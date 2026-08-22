#!/usr/bin/with-contenv bashio
# app.py leser /data/options.json direkte - enklere enn a mate lister gjennom bashio.
bashio::log.info "Garasjeport Web $(bashio::addon.version) starter på port 8099"
exec python3 -u /app.py
