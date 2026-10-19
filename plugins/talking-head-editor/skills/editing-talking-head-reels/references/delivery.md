# Delivery

## Hand-off
Send the render (files over ~500 MB don't reach phones: say so) plus a short list: what changed, what's still open (claim flags,
missing photos, consent), and where the Resolve project is. Keep the Resolve and AE projects; they are the editable source.

## Landing page / website
1. `python3 web_encode.py render/<OUT>_final.mp4 --poster-at <seconds> --out web/<name>.mp4`
   720p H.264, CRF 23 capped at ~1.1 Mbit/s, AAC 128k, `+faststart`. A 7-minute VSL lands near 40 MB. Pick a poster frame
   that sells: the guarantee or offer card on screen beats a mid-word face.
2. Put both files where the site serves static media (e.g. a Next.js `public/` folder) and point the page's video player at
   them. Use the site's own branch-and-review process: build it, push the branch, get the preview URL.
3. Verify on the preview URL, not locally: the page HTML references the new files; the video answers a range request with
   HTTP 206 and `content-type: video/mp4`; the poster loads; the player shows on a phone-width screenshot.
4. Go live only when the owner says so, then verify again on the production domain (same three checks) and that the
   production deployment came from git.
5. Leave other pages that used the old video alone unless asked; keep the old file if anything still references it.

## YouTube
Upload the full-quality H.264 render, not the web encode. Chapters from the section starts; captions as an .srt from the
caption groups if wanted.
