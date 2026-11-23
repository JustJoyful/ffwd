set -e
cd /home/joydeep/Projects/ffmpeg-agent
source data/tools/mlc-env.sh
M3=data/mlc/_src/m3
M1=data/mlc/_src/m1
conv() { # name hf quant
  python -m mlc_llm convert_weight $2 --quantization $3 --device ${DEV:-cuda} -o data/mlc/$1 2>&1 | grep -v Warning
  python -m mlc_llm gen_config $2 --quantization $3 --conv-template qwen3 -o data/mlc/$1 2>&1 | grep -v Warning
}
conv m3-q0f16 $M3 q0f16
conv m3-q4f16_1 $M3 q4f16_1
conv m1-q4f16_1 $M1 q4f16_1
echo ALLDONE
