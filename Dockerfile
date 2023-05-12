FROM python:3.8.16-slim

ENV LANG="C.UTF-8" \
    LC_ALL="C.UTF-8" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1 \
    LIBGL_ALWAYS_INDIRECT=1

RUN adduser --quiet --disabled-password qtuser && \
    usermod -a -G audio qtuser && apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-pyqt5 && \
    pip install -U pip setuptools wheel

WORKDIR /opt/app/

COPY requirements.txt '/opt/app/'

RUN pip install -r requirements.txt

COPY *.so core.py main.py toupcam.py scanner_camera.py '/opt/app/'

ENTRYPOINT ["python", "main.py"]
