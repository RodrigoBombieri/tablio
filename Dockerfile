FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/tablio
RUN groupadd --system tablio && useradd --system --gid tablio --home /srv/tablio tablio
COPY --chown=tablio:tablio app/ app/
COPY --chown=tablio:tablio web/ web/
RUN mkdir -p /private/data /private/uploads /backups && chown -R tablio:tablio /private /backups
USER tablio
EXPOSE 8000
CMD ["python", "-m", "app.server"]
