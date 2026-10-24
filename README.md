# Montage Uploader

Drop one finished Montager video (`LM_CS2_V9.0.1_2026-10-24.mp4`) onto the window or onto the desktop shortcut. The app then:

1. finds the song and game in Montager's own data (read-only: the plan saved next to the render, `montage.log`, `used_songs.json`, and the playlist CSV). If it can't find them, it asks once in a small box and remembers your answer.
2. builds the title `<Song> | <Game> Montage`, for example `Azure Lane | CS2 Montage`, and a short description from `description_template.txt`.
3. saves 3 thumbnails (1280x720 JPG, under 2 MB) to `<video folder>\thumbnails\`. They are frames from the montage's own intro (the song title over the blurred gameplay); the sharpest one is #1.
4. uploads the video to your channel as **PRIVATE** with a resumable upload, sets thumbnail #1, and shows the link. After the upload you can switch to #2 or #3 with **Use #2 / #3 instead**.

It never writes to Montager's folders.

## Install (once)

1. Python 3.10 or newer from python.org, with "Add to PATH" ticked. ffmpeg is already installed for Montager.
2. `git clone https://github.com/fireaxe77/uploader.git C:\Users\fireaxe\Desktop\montage-uploader`
3. Double-click `Install.bat`. It installs the packages and runs the check.
4. Double-click `Create_Desktop_Shortcut.vbs`. It puts "Montage Uploader" on the desktop.

## One-time Google setup (in your browser)

1. Create a project named "Montage Uploader": https://console.cloud.google.com/projectcreate
2. Enable the **YouTube Data API v3** in that project: https://console.cloud.google.com/apis/library/youtube.googleapis.com
3. Set up the consent screen: https://console.cloud.google.com/auth/overview
   - Click **Get started**. App name: Montage Uploader. Support email: yours. Audience: **External**. Contact: your email. Then **Create**.
   - Go to **Audience** (https://console.cloud.google.com/auth/audience) and click **Publish app**, then confirm. Do **not** submit it for verification.
   - Why publish: an app left in "Testing" loses its login every 7 days.
4. Create the login client: https://console.cloud.google.com/auth/clients
   - Click **Create client**. Type: **Desktop app**. Name: Montage Uploader. Then **Create**.
   - Click **Download JSON**. Save the file as `C:\Users\fireaxe\Desktop\montage-uploader\secrets\client_secret.json`.
5. Log in on the first drop. The browser opens Google's login.
   - Choose your channel's account.
   - On "Google hasn't verified this app", click **Advanced**, then **Go to Montage Uploader**, then **Continue**.
   - The login is saved to `secrets\token.json`.
6. Optional, for custom thumbnails: phone-verify the channel at https://www.youtube.com/verify. Until you do, the video still uploads; the app keeps the thumbnail files and tells you.

**Important: uploads stay private.** Google locks every video uploaded through an API project created after 28 July 2020 to *private* unless the project passes Google's audit. That includes this app's project.

- You **cannot** switch these videos to public in YouTube Studio.
- To make a montage public, upload that file by hand in YouTube Studio. The title, description and thumbnails are ready in the app window and the `thumbnails` folder.
- The other option is Google's audit ("YouTube API Services - Audit and Quota Extension" form), which this app does not apply for.

## Use

- Drop the .mp4 onto the desktop shortcut, onto `Montage Uploader.bat`, or onto the open window. You can also click the drop area to choose a file.
- `python app.py --dry-run <video>` does everything except the upload.
- `python app.py --prepare <video>` does the same without a window: it prints the title and description and writes the thumbnails.
- `python app.py --check` runs the first-run check: Python, packages, ffmpeg, client_secret.json, Montager folder.

## Settings (`settings.json`, created on first run)

| key | meaning |
|---|---|
| `montager_data_dir` | Montager's `montage_data` folder (default `C:\Users\fireaxe\Desktop\CLAUDECODE\montager\montage_data`) |
| `description_template` | the description text file (default `description_template.txt`; edit it freely) |
| `privacy` | `private` (default) |
| `thumbnail_folder_name` / `thumbnail_output_dir` | where the 3 thumbnails go (default: a `thumbnails` folder next to the video) |

## Errors

All errors appear as plain text in the window.

- **Quota used up:** try again tomorrow. The quota resets at midnight Pacific and allows several uploads a day.
- **Connection drop:** the upload resumes by itself, retrying up to 12 times.
- **Wrong file:** a non-video file, a folder, or a half-written `.part.mp4`.
- **Expired login:** the browser login opens again.
- **Same file dropped twice:** the app asks before uploading it again.

## Privacy

`secrets\` (client_secret.json, token.json), `settings.json`, `memory.json`, `uploads.json` and `logs\` are in `.gitignore`. Credentials are never logged or uploaded.

## Tests

`python tests/test_all.py <path to the montager repo>` builds a test montage from Montager's own frames and checks the song lookup, the text, the thumbnails, wrong files, and the upload logic against a fake YouTube (network drop, 503, unverified-channel thumbnail, quota).
