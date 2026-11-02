# Attendance-Snap

A Flask + MySQL attendance project for student and teacher accounts. It includes
account registration/login, student photo capture, campus GPS geofencing,
attendance history, teacher attendance records and user-selected avatar styles.

## Requirements

- Python 3.10 or newer
- MySQL Server
- A modern browser with camera and location permissions

## Setup on Windows (PowerShell)

1. Extract the project ZIP.
2. Open PowerShell in the `Attendance-Snap` project folder.
3. Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

4. Install dependencies:

   ```powershell
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

5. In MySQL Workbench, open and execute `database/schema.sql`.
6. Copy `.env.example` to `.env` in the project root. Set a new random
   `FLASK_SECRET_KEY` (at least 32 characters) and the correct MySQL password.
   Keep `.env` private and do not commit it to GitHub.
7. Start the app from the project root:

   ```powershell
   python app.py
   ```

8. Open http://127.0.0.1:5000 in your browser.

## Configuration

The `.env` file controls database connection details, server port and campus
coordinates/radius. Default campus coordinates are latitude
`16.9951463487529`, longitude `81.79950858287084`, radius `100` metres,
and maximum accepted browser GPS accuracy `50` metres. Adjust these values
to the institution's authorized location.

## Features

- Student and teacher registration/login.
- Student photo capture using the browser camera.
- Browser GPS check against the configured campus geofence.
- One attendance entry per student per calendar day (Asia/Kolkata).
- Student attendance history.
- Teacher attendance records, optionally filtered by class/section.
- User-selected avatar style; the app does not infer identity from a photo.

## Important notes

- Camera and geolocation work on `localhost` or on an HTTPS deployment.
- Browser GPS can be inaccurate or spoofed; geofencing alone does not prove
  physical presence.
- Teacher registration is open in this learning version. Restrict it to
  approved staff before real institutional use.
- Photos are stored in `uploads/`; implement retention/deletion controls and
  obtain informed consent before storing real student photos.
- This uses Flask's development server. Do not expose it directly to the
  public internet; use a production WSGI server, HTTPS, backups and a security
  review for deployment.
