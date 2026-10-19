#!/bin/bash
# DIAG: fetch manifests from Public ECR anonymously and with the credentials from `sudo finch login`.
# Prints HTTP status codes and error bodies only; tokens are never printed.
AUTH=$(sudo jq -r '.auths["public.ecr.aws"].auth // empty' /root/.docker/config.json 2>/dev/null)
ACCEPT='application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.v2+json'

fetch() {
  local mode=$1 repo=$2 ref=$3 token body code
  if [ "$mode" = authenticated ]; then
    token=$(curl -s -H "Authorization: Basic $AUTH" "https://public.ecr.aws/token/?service=public.ecr.aws&scope=repository:$repo:pull" | jq -r .token)
  else
    token=$(curl -s "https://public.ecr.aws/token/?service=public.ecr.aws&scope=repository:$repo:pull" | jq -r .token)
  fi
  body=$(mktemp)
  code=$(curl -s -o "$body" -w '%{http_code}' -H "Authorization: Bearer $token" -H "Accept: $ACCEPT" "https://public.ecr.aws/v2/$repo/manifests/$ref")
  echo "$mode $repo@$ref -> $code $( [ "$code" = 200 ] || head -c 200 "$body")"
  rm -f "$body"
}

echo "=== Public ECR manifest fetches (credentials from finch login: $([ -n "$AUTH" ] && echo present || echo missing)) ==="
for mode in anonymous authenticated; do
  fetch $mode durable-functions/aws-durable-execution-emulator latest
  fetch $mode durable-functions/aws-durable-execution-emulator sha256:c7a010af4cba9a33fc914188954e00cfc34127e5c4c598b065229d0cb3dd8aaa
  fetch $mode lambda/python 3.13-x86_64
done
