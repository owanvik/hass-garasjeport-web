#!/usr/bin/with-contenv bashio
export GP_USERNAME="$(bashio::config 'username')"
export GP_ENTITY="$(bashio::config 'entity_id')"
export GP_COOLDOWN="$(bashio::config 'cooldown_seconds')"
bashio::log.info "Garasjeport Web starter på port 8099 (entity: ${GP_ENTITY})"
exec python3 -u /app.py
