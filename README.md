# Pick Dashboard 5.2

Multi-user warehouse route picking dashboard built with Flask.

## Quick start (Windows)

```
double-click run-pick-dashboard.bat
```

## Manual start

```bash
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 in your browser.

## Default login

- **Username:** zeck
- **Password:** zeeman1258

## Files

| File | Purpose |
|---|---|
| app.py | Main Flask application |
| wsgi.py | Gunicorn entry point |
| gunicorn.conf.py | Gunicorn config |
| requirements.txt | Python dependencies |
| run-pick-dashboard.bat | Windows one-click launcher |
| DEPLOYMENT.txt | Linux/server deployment notes |
| FREE_HOSTING_TUTORIAL.txt | Render/PythonAnywhere hosting guide |

## Deployment

See `DEPLOYMENT.txt` and `FREE_HOSTING_TUTORIAL.txt` for server and free-hosting instructions.
