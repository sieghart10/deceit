# Fake News Detector
News detector that checks if news or posts are real or fake using simple Bag of Words (BoW) + Naive Bayes and scoring algorithms

<p align="center">
  <img src="https://res.cloudinary.com/izynegallardo/image/upload/v1758404107/1c9b736a-cf5d-418a-a27a-8e39c7b94c4e.png" width="200" />
  <img src="https://res.cloudinary.com/izynegallardo/image/upload/v1758404232/2b75f86b-5266-4999-b64c-e31f3ed0a015.png" width="200" />
  <img src="https://res.cloudinary.com/izynegallardo/image/upload/v1758405107/verifyImage_bopipp.png" width="200" />
  <img src="https://res.cloudinary.com/izynegallardo/image/upload/v1758405228/f9f6fb59-53ae-4683-a580-fbae461ab123.png" width="200" />
</p>


## Features
- Platform Detection – Automatically detects if you’re on supported sites (e.g., Facebook, news pages).

- Enable/Disable Toggle – Turn the extension on or off anytime.

- Link Verification – Paste any article links to check if it’s fake or real.

- Active Platforms – Enable/ Disable facebook checkbox if .

- One-Click Verification – Check if selected text or images are real or fake.(underdevelopment)

- Context Menu Support – Right-click on content and choose “Verify” directly.

- Toast Notifications – Get instant result with icons (loading, verified, suspicious, error).


## Project Structure

```
backend/         # FastAPI backend, ML models, utilities
extension/       # Chrome extension (HTML, JS, CSS)
tools/           # Scraper scripts and notebooks
```

## Getting Started

### 1. Backend API

Install dependencies:
```sh
pip install -r requirements.txt
```

Run the API server:
```sh
cd backend
python app.py
```

### 2. Chrome Extension

- Load `extension/` as an unpacked extension in Chrome.
- Make sure the backend API is running locally.

### 3. Scraping Data

Use scripts in `tools/` to collect and update datasets:
```sh
python tools/rappler_scraper.py
python tools/inquirer-scraper.py
# etc.
```

## Usage

- Select text or links in your browser and use right click to open the extension contextMenu  to verify.
- The extension communicates with the backend API for predictions.
- Results are shown as toast notifications and in the popup.

## Contributors

- [Gallardo, Izyne Howie](https://github.com/sieghart10)
- [Sta. Ana, Eleina Anne](https://github.com/staanaeleina)

 ## License

See [LICENSE](LICENSE).
