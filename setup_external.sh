#!/usr/bin/env bash
set -e

mkdir -p external

if [ ! -d external/ACE-Step-1.5 ]; then
  git clone https://github.com/ace-step/ACE-Step-1.5 external/ACE-Step-1.5
fi

if [ ! -d external/seed-vc ]; then
  git clone https://github.com/Plachtaa/seed-vc external/seed-vc
fi

if [ ! -d external/MuseTalk ]; then
  git clone https://github.com/TMElyralab/MuseTalk external/MuseTalk
fi

if [ ! -d external/LatentSync ]; then
  git clone https://github.com/bytedance/LatentSync external/LatentSync
fi

if [ ! -d external/echomimic_v2 ]; then
  git clone https://github.com/antgroup/echomimic_v2 external/echomimic_v2
fi

if [ ! -d external/echomimic_v3 ]; then
  git clone https://github.com/antgroup/echomimic_v3 external/echomimic_v3
fi

if [ ! -d external/hallo3 ]; then
  git clone https://github.com/fudan-generative-vision/hallo3 external/hallo3
fi

echo "External repos cloned. Install each repo requirements if their README asks for extra steps."
echo "Video backends: bash scripts/setup_latentsync.sh | setup_echomimic.sh | setup_hallo3.sh | setup_musetalk.sh"
