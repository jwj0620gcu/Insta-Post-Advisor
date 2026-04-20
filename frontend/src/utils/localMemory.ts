/**
 * 브라우저 로컬 진단 히스토리(IndexedDB).
 * 데이터는 기기에만 저장되며 서버로 업로드되지 않는다.
 *
 * - 진단 1건당 전체 report를 1개 저장한다.
 * - 기본 키는 `local-*`(마이그레이션 잔여 `legacy-*` 포함)이다.
 */
import type { DiagnoseResult } from "./api";

const DB_NAME = "insta-advisor_local_memory";
const DB_VERSION = 1;
const STORE = "diagnoses";

export interface LocalDiagnosisRecord {
  /** 기본 키: local-${uuid} 또는 마이그레이션 잔여 id */
  id: string;
  /** 보존용 필드. 순수 로컬 모드에서는 항상 null */
  serverId: string | null;
  title: string;
  category: string;
  overall_score: number;
  grade: string;
  createdAt: number;
  report: DiagnoseResult;
  params: Record<string, unknown>;
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onerror = () => reject(req.error ?? new Error("indexedDB open failed"));
    req.onsuccess = () => resolve(req.result);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: "id" });
      }
    };
  });
}

/**
 * 구버전 localStorage 데이터를 최대 약 10건까지 1회 마이그레이션한다.
 */
export async function migrateLegacyLocalStorage(): Promise<void> {
  try {
    const raw = localStorage.getItem("insta-advisor_history");
    if (!raw) return;
    const arr = JSON.parse(raw) as Array<{
      title: string;
      score: number;
      grade: string;
      category: string;
      date: number;
      report: DiagnoseResult;
      params?: Record<string, unknown>;
    }>;
    if (!Array.isArray(arr) || arr.length === 0) {
      localStorage.removeItem("insta-advisor_history");
      return;
    }
    const db = await openDb();
    const tx = db.transaction(STORE, "readwrite");
    const os = tx.objectStore(STORE);
    for (const h of arr) {
      const id = `legacy-${h.date}-${Math.random().toString(36).slice(2, 10)}`;
      os.put({
        id,
        serverId: null,
        title: h.title,
        category: h.category,
        overall_score: h.score,
        grade: h.grade,
        createdAt: h.date,
        report: h.report,
        params: h.params ?? {},
      } satisfies LocalDiagnosisRecord);
    }
    await new Promise<void>((res, rej) => {
      tx.oncomplete = () => res();
      tx.onerror = () => rej(tx.error ?? new Error("tx failed"));
    });
    localStorage.removeItem("insta-advisor_history");
  } catch {
    /* 마이그레이션 실패 시에도 메인 흐름은 계속 진행 */
  }
}

export async function putLocalDiagnosis(rec: LocalDiagnosisRecord): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error ?? new Error("put failed"));
    tx.objectStore(STORE).put(rec);
  });
}

export async function getLocalDiagnosis(id: string): Promise<LocalDiagnosisRecord | null> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readonly");
    const req = tx.objectStore(STORE).get(id);
    req.onsuccess = () => resolve((req.result as LocalDiagnosisRecord | undefined) ?? null);
    req.onerror = () => reject(req.error ?? new Error("get failed"));
  });
}

export async function listLocalDiagnoses(): Promise<LocalDiagnosisRecord[]> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readonly");
    const req = tx.objectStore(STORE).getAll();
    req.onsuccess = () => resolve((req.result as LocalDiagnosisRecord[]) ?? []);
    req.onerror = () => reject(req.error ?? new Error("getAll failed"));
  });
}

export async function deleteLocalDiagnosis(id: string): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error ?? new Error("delete failed"));
    tx.objectStore(STORE).delete(id);
  });
}

/** @returns 새 로컬 기록 id */
export function createLocalDiagnosisId(): string {
  return `local-${crypto.randomUUID()}`;
}

/**
 * @deprecated {@link createLocalDiagnosisId} 사용
 */
export function createPendingId(): string {
  return createLocalDiagnosisId();
}

export function localRecordToListItem(r: LocalDiagnosisRecord): import("./api").HistoryListItem {
  return {
    id: r.id,
    title: r.title,
    category: r.category,
    overall_score: r.overall_score,
    grade: r.grade,
    created_at: new Date(r.createdAt).toISOString(),
  };
}
