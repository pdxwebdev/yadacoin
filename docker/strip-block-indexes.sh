#!/bin/sh
meta="$1"
if [ -f "$meta" ]; then
  jq '(.indexes // []) |= map(select(.name != "__txn_id_inputs_id" and .name != "__txn_public_key_inputs_id"))' "$meta" > "$meta.tmp" && mv "$meta.tmp" "$meta"
fi
