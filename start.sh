set -e
cd /root/build_agent || exit 1
source /root/build_agent/.env || exit 1

nohup /root/build_agent/.venv/bin/python run.py --all > log 2>&1 &

disown $!

exit 0