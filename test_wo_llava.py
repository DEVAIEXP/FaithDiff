import torch.cuda
import argparse
from FaithDiff.create_FaithDiff_model import FaithDiff_pipeline
from PIL import Image
from CKPT_PTH import LLAVA_MODEL_PATH, SDXL_PATH, FAITHDIFF_PATH, VAE_FP16_PATH
from utils.color_fix import wavelet_color_fix, adain_color_fix
from utils.image_process import check_image_size
import numpy as np
import os
import cv2
import json


    
# hyparams here
parser = argparse.ArgumentParser()
parser.add_argument("--img_dir", type=str)
parser.add_argument("--save_dir", type=str)
parser.add_argument("--json_dir", type=str)
parser.add_argument("--upscale", type=int, default=4)
parser.add_argument("--seed", type=int, default=42)
parser.add_argument("--min_size", type=int, default=1024)
parser.add_argument("--tiled_overlap", type=float, default=0.5)
parser.add_argument("--tiled_size", type=int, default=1024)
parser.add_argument("--guidance_scale", type=float, default=5)
parser.add_argument("--num_inference_steps", type=int, default=20)
parser.add_argument("--use_tile_vae", action='store_true', default=False)
parser.add_argument("--vae_tiled_overlap", type=float, default=0.25)
parser.add_argument("--vae_tiled_size", type=int, default=1024)
parser.add_argument("--color_fix", type=str, choices=['wavelet', 'adain', 'nofix'], default='adain')
parser.add_argument("--start_point", type=str, choices=['lr', 'noise'], default='lr')
args = parser.parse_args()
print(args)

# load FaithDiff FP16
pipe = FaithDiff_pipeline(sdxl_path=SDXL_PATH, VAE_FP16_path=VAE_FP16_PATH, FaithDiff_path=FAITHDIFF_PATH)
pipe = pipe.to('cuda')

if args.use_tile_vae:
    pipe.denoise_encoder.tile_sample_min_size=args.vae_tiled_size
    pipe.denoise_encoder.tile_overlap_factor=args.vae_tiled_overlap
    pipe.denoise_encoder.enable_tiling()
    pipe.vae.config.sample_size=args.vae_tiled_size
    pipe.vae.tile_overlap_factor = args.vae_tiled_overlap
    pipe.vae.enable_tiling()




os.makedirs(args.save_dir, exist_ok=True)

exist_file = os.listdir(args.save_dir)
    
for file_name in sorted(os.listdir(args.img_dir)):
    img_name = file_name.split('.')[0]
    if f"{img_name}.png" in exist_file:
        print(f"{img_name}.png exist")
        continue
    else:
        print(img_name)

    image = Image.open(os.path.join(args.img_dir,file_name)).convert('RGB')

    json_file = json.load(open(os.path.join(args.json_dir,img_name+'.json'))) 
    init_text = json_file["caption"]
    words = init_text.split()
    words = words[3:]
    words[0] = words[0].capitalize()
    text = ' '.join(words)
    text = text.split('. ')
    text = '. '.join(text[:2]) + '.'  


    # step 2: Restoration
    w, h = image.size
    w *= args.upscale
    h *= args.upscale
    image = image.resize((w, h), Image.LANCZOS)
    input_image, width_init, height_init, width_now, height_now = check_image_size(image)
    prompt_init = text 
    negative_prompt_init = ""
    generator = torch.Generator(device='cuda').manual_seed(args.seed)
    gen_image = pipe(lr_img=input_image, prompt = prompt_init, negative_prompt = negative_prompt_init, num_inference_steps=args.num_inference_steps, guidance_scale=args.guidance_scale, generator=generator, start_point=args.start_point, height = height_now, width=width_now, overlap=args.tiled_overlap, target_size=(args.tiled_size, args.tiled_size)).images[0]
    path = os.path.join(args.save_dir, img_name+'.png')
    cropped_image = gen_image.crop((0, 0, width_init, height_init))

    if args.color_fix == 'nofix':
        out_image = cropped_image
    else:
        if args.color_fix == 'wavelet':
            out_image = wavelet_color_fix(cropped_image, image)
        elif args.color_fix == 'adain':
            out_image = adain_color_fix(cropped_image, image)
    out_image.save(path)

