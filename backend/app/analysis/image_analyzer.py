"""
커버 이미지 분석 모듈.
OpenCV 기반으로 구도, 색감, 얼굴 검출 등 시각 특성을 계산한다.
"""
from __future__ import annotations

import io
import logging

import numpy as np

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

from PIL import Image

logger = logging.getLogger(__name__)


class ImageAnalyzer:
    """커버 이미지의 시각 특성을 분석한다."""

    def analyze(self, image_bytes: bytes) -> dict:
        """
        이미지를 분석해 시각 지표를 반환한다.

        @param image_bytes - 원본 이미지 바이트
        @returns saturation, text_ratio, has_face, brightness, composition 등을 담은 dict
        """
        img_pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_np = np.array(img_pil)

        composition = self._analyze_composition(img_np)
        color_harmony = self._analyze_color_harmony(img_np)

        result = {
            "width": img_pil.width,
            "height": img_pil.height,
            "aspect_ratio": round(img_pil.width / max(img_pil.height, 1), 2),
            "saturation": self._calc_saturation(img_np),
            "brightness": self._calc_brightness(img_np),
            "contrast": self._calc_contrast(img_np),
            "has_face": self._detect_face(img_np),
            "face_position": self._detect_face_position(img_np),
            "text_ratio": self._estimate_text_ratio(img_np),
            "dominant_colors": self._get_dominant_colors(img_np),
            "color_harmony": color_harmony,
            "composition": composition,
            "visual_complexity": self._calc_visual_complexity(img_np),
            "narrative": self._build_narrative(img_pil, composition, color_harmony),
        }
        return result

    def _calc_contrast(self, img_np: np.ndarray) -> float:
        """밝기 대비(표준편차 / 255)를 계산한다."""
        gray = np.mean(img_np, axis=2)
        return round(float(np.std(gray) / 255.0), 3)

    def _detect_face_position(self, img_np: np.ndarray) -> str | None:
        """얼굴 위치를 3x3 영역 기준으로 추정한다."""
        if not CV2_AVAILABLE:
            return None
        try:
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            faces = face_cascade.detectMultiScale(gray, 1.3, 5)
            if len(faces) == 0:
                return None
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            cx, cy = x + w / 2, y + h / 2
            img_h, img_w = img_np.shape[:2]
            col = "left" if cx < img_w / 3 else ("right" if cx > img_w * 2 / 3 else "center")
            row = "top" if cy < img_h / 3 else ("bottom" if cy > img_h * 2 / 3 else "center")
            return f"{row}{col}"
        except Exception:
            return None

    def _analyze_composition(self, img_np: np.ndarray) -> dict:
        """
        구도 특성(삼분할 에너지 분포, 중심 치우침, 시각 초점)을 분석한다.
        """
        h, w = img_np.shape[:2]
        gray = np.mean(img_np, axis=2)

        third_h, third_w = h // 3, w // 3
        grid_weights = []
        for r in range(3):
            row_weights = []
            for c in range(3):
                block = gray[r * third_h:(r + 1) * third_h, c * third_w:(c + 1) * third_w]
                energy = float(np.std(block))
                row_weights.append(round(energy, 1))
            grid_weights.append(row_weights)

        max_energy = 0.0
        focus_r, focus_c = 1, 1
        for r in range(3):
            for c in range(3):
                if grid_weights[r][c] > max_energy:
                    max_energy = grid_weights[r][c]
                    focus_r, focus_c = r, c

        row_labels = ["top", "center", "bottom"]
        col_labels = ["left", "center", "right"]
        focus_desc = f"{row_labels[focus_r]}{col_labels[focus_c]}"

        total_energy = sum(sum(row) for row in grid_weights)
        if total_energy > 0:
            center_energy = grid_weights[1][1]
            center_ratio = round(center_energy / total_energy, 2)
        else:
            center_ratio = 0.33

        is_centered = center_ratio > 0.15
        uses_rule_of_thirds = not is_centered and focus_desc != "centercenter"

        return {
            "grid_energy": grid_weights,
            "focus_region": focus_desc,
            "center_weight": center_ratio,
            "is_centered_composition": is_centered,
            "uses_rule_of_thirds": uses_rule_of_thirds,
            "layout": "centered composition" if is_centered else f"off-center composition({focus_desc})",
        }

    def _analyze_color_harmony(self, img_np: np.ndarray) -> dict:
        """색조 분포/난색·한색/채도 분산을 기반으로 색 조화를 분석한다."""
        if not CV2_AVAILABLE:
            r_mean = float(np.mean(img_np[:, :, 0]))
            b_mean = float(np.mean(img_np[:, :, 2]))
            tone = "warm tone" if r_mean > b_mean + 15 else ("cool tone" if b_mean > r_mean + 15 else "neutral tone")
            return {"tone": tone, "saturation_variance": 0.0, "hue_spread": 0.0}

        hsv = cv2.cvtColor(img_np, cv2.COLOR_RGB2HSV)
        hue = hsv[:, :, 0].astype(float) * 2
        sat = hsv[:, :, 1].astype(float) / 255.0

        hue_std = float(np.std(hue))
        sat_var = round(float(np.var(sat)), 4)

        mean_hue = float(np.mean(hue))
        if 20 < mean_hue < 80:
            tone = "warm tone"
        elif 180 < mean_hue < 280:
            tone = "cool tone"
        else:
            tone = "neutral tone"

        if hue_std < 30:
            harmony_level = "monochrome (high harmony)"
        elif hue_std < 60:
            harmony_level = "analogous (medium harmony)"
        else:
            harmony_level = "multi-color (rich palette)"

        return {
            "tone": tone,
            "harmony_level": harmony_level,
            "saturation_variance": round(sat_var, 4),
            "hue_spread": round(hue_std, 1),
        }

    def _calc_visual_complexity(self, img_np: np.ndarray) -> float:
        """
        시각 복잡도(0-1)를 계산한다.
        값이 높을수록 장면 요소가 많고, 낮을수록 단순한 이미지다.
        """
        if not CV2_AVAILABLE:
            gray = np.mean(img_np, axis=2).astype(np.uint8)
            dx = np.abs(np.diff(gray, axis=1)).mean()
            dy = np.abs(np.diff(gray, axis=0)).mean()
            return round(min((dx + dy) / 100.0, 1.0), 3)

        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / (edges.shape[0] * edges.shape[1])
        return round(min(edge_density * 3, 1.0), 3)

    def _build_narrative(self, img_pil: Image.Image, composition: dict, color_harmony: dict) -> str:
        """에이전트 프롬프트에 사용할 커버 시각 서술문을 생성한다."""
        w, h = img_pil.width, img_pil.height
        if w / h > 1.2:
            shape = "landscape"
        elif h / w > 1.2:
            shape = "portrait (mobile full-screen friendly)"
        else:
            shape = "near square"

        parts = [
            f"Cover size: {w}x{h}, {shape}.",
            f"Composition: {composition.get('layout', 'unknown')}, focus at {composition.get('focus_region', 'center')}.",
            f"Overall color tone: {color_harmony.get('tone', 'neutral tone')}",
        ]
        harmony = color_harmony.get("harmony_level")
        if harmony:
            parts.append(f", {harmony}.")
        else:
            parts.append(".")

        return "".join(parts)

    def _calc_saturation(self, img_np: np.ndarray) -> float:
        """평균 채도(0-1)를 계산한다."""
        if not CV2_AVAILABLE:
            r, g, b = img_np[:,:,0], img_np[:,:,1], img_np[:,:,2]
            max_c = np.maximum(np.maximum(r, g), b).astype(float)
            min_c = np.minimum(np.minimum(r, g), b).astype(float)
            diff = max_c - min_c
            sat = np.where(max_c > 0, diff / max_c, 0)
            return round(float(np.mean(sat)), 3)

        hsv = cv2.cvtColor(img_np, cv2.COLOR_RGB2HSV)
        return round(float(np.mean(hsv[:, :, 1]) / 255.0), 3)

    def _calc_brightness(self, img_np: np.ndarray) -> float:
        """평균 밝기(0-1)를 계산한다."""
        gray = np.mean(img_np, axis=2)
        return round(float(np.mean(gray) / 255.0), 3)

    def _detect_face(self, img_np: np.ndarray) -> bool:
        """이미지 내 얼굴 존재 여부를 반환한다."""
        if not CV2_AVAILABLE:
            return False
        try:
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            faces = face_cascade.detectMultiScale(gray, 1.3, 5)
            return len(faces) > 0
        except Exception:
            return False

    def _estimate_text_ratio(self, img_np: np.ndarray) -> float:
        """
        커버 내 텍스트 영역 비율을 추정한다.
        에지 검출과 팽창 연산을 이용한 근사치다.
        """
        if not CV2_AVAILABLE:
            return 0.15

        try:
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            dilated = cv2.dilate(edges, kernel, iterations=2)
            text_pixels = np.sum(dilated > 0)
            total_pixels = dilated.shape[0] * dilated.shape[1]
            return round(text_pixels / total_pixels, 3)
        except Exception:
            return 0.15

    def _get_dominant_colors(self, img_np: np.ndarray, k: int = 3) -> list[str]:
        """주요 색상을 추출한다(단순화: 블록 평균색 기반)."""
        h, w = img_np.shape[:2]
        block_h, block_w = h // 3, w // 3
        colors = []
        for i in range(3):
            row = i * block_h
            col = i * block_w
            block = img_np[row:row+block_h, col:col+block_w]
            avg_color = block.mean(axis=(0, 1)).astype(int)
            hex_color = "#{:02x}{:02x}{:02x}".format(*avg_color)
            colors.append(hex_color)
        return colors
