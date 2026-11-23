cd /home/joydeep/Projects/ffmpeg-agent
source data/tools/mlc-env.sh
export PATH=/opt/cuda/bin:$PATH
for m in ${@:-m3-q4f16_1}; do
  python -m mlc_llm compile data/mlc/$m --device cuda --opt O2 -o data/mlc/$m/lib-cuda.so 2>&1 | grep -a -v Warning
  echo "DONE $m"
done
