# Source CSV Guide (for public crawl)

`make modela-merge`는 이 폴더의 `*.csv`를 읽어 `raw_posts.csv`로 정규화/병합합니다.

## 권장 최소 헤더 (공개 크롤링)
- `post_id`
- `created_at` (예: `2026-04-10 14:20:00` 또는 ISO8601)
- `category` (`food/fashion/fitness/business/lifestyle/travel/education/shop`)
- `format` (`reels/carousel/single` 또는 reel/video/photo/album 등 별칭)
- `caption`
- `hashtags_count`
- `media_count`
- `followers`
- `likes`
- `comments`
- `views` (릴스면 권장)

## 별칭 허용 (자동 매핑)
- `date`, `published_at`, `timestamp` -> `created_at`
- `type`, `media_type`, `post_type` -> `format`
- `text`, `content`, `description` -> `caption`
- `hashtag_count`, `tag_count` -> `hashtags_count`
- `follower_count`, `followers_count` -> `followers`
- `like_count` -> `likes`
- `comment_count` -> `comments`
- `video_views`, `play_count`, `plays` -> `views`

## 실행
```bash
make modela-prep-crawl
```
