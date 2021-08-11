FROM python:3-slim

ENV USERNAME=panoptes
ENV PORT=6565

RUN apt-get update && \
    apt-get install -y --no-install-recommends gphoto2

RUN pip install fastapi pydantic uvicorn[standard]

# Create user, image directory, and update permissions for usb.
RUN useradd --no-create-home -G plugdev ${USERNAME} && \
    mkdir -p /images && chmod 777 /images && \
    mkdir -p /app && chmod 777 /app

WORKDIR /app
USER "${USERNAME}"
COPY camera.py .

EXPOSE 6565

CMD uvicorn camera:app --host 0.0.0.0 --port "${PORT}"