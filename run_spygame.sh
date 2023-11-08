set -e
set -u

# SPYGAME_PATH=$(realpath `dirname $0`)
SPYGAME_PATH=/Your-Workspace/SpyGame

python3 $SPYGAME_PATH/spygame.py \
    --host-agent gpt-3.5-turbo \
    --guest-agent gpt-3.5-turbo \
    --temperature 0.3 \
    --num-players 4
