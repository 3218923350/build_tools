set -e
cd /root/build_tools || exit 1
source /root/build_tools/.env || exit 1

nohup /root/build_tools/.venv/bin/python run.py --all > log 2>&1 &

disown $!

exit 0