# Subtitle Generator Backend

This is a Django-based backend for generating English subtitles from AVI videos.

## Setup

1. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run migrations:
   ```
   python manage.py migrate
   ```

4. Start the development server:
   ```
   python manage.py runserver
   ```

## API Endpoints

- `POST /api/upload/`: Upload a video file and start subtitle generation
- `GET /api/download/<id>/`: Download the generated subtitle file

## Dependencies

- Django
- Django REST Framework
- SpeechRecognition
- MoviePy
- PySRT