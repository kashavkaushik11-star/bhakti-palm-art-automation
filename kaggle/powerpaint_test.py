import os, sys, subprocess, urllib.request
from pathlib import Path
WORK=Path("/kaggle/working"); REF=WORK/"palm_reference.jpg.jpg"; OUT=WORK/"palm_art.png"; CLEAN=WORK/"clean_hand.png"
RAW_REF="https://raw.githubusercontent.com/kashavkaushik11-star/bhakti-palm-art-automation/9ab089b8b6b09cad89d45b05fa252c7ff4b67f26/palm_reference.jpg.jpg"
def run(c): subprocess.run(c,check=True)
run([sys.executable,"-m","pip","install","-q","accelerate","controlnet-aux==0.0.3","diffusers==0.27.0","gradio==3.41.0","mmengine","opencv-python","transformers==4.28.0","huggingface_hub==0.25.0","safetensors"])
if not REF.exists(): urllib.request.urlretrieve(RAW_REF,REF)
repo_dir=WORK/"PowerPaint"
if not repo_dir.exists(): run(["git","clone","--depth","1","https://github.com/open-mmlab/PowerPaint.git",str(repo_dir)])
from huggingface_hub import snapshot_download
weights=WORK/"powerpaint_v1"
if not weights.exists(): snapshot_download(repo_id="JunhaoZhuang/PowerPaint-v1",local_dir=str(weights),allow_patterns=["*.json","*.safetensors","*.md",".gitattributes"])
sys.path.insert(0,str(repo_dir))
from app import PowerPaintController
from PIL import Image
import cv2,numpy as np,torch
img=Image.open(REF).convert("RGB"); img.save(WORK/"reference_used.png")
arr=np.array(img); h,w=arr.shape[:2]
gc=np.full((h,w),cv2.GC_BGD,np.uint8); gc[8:h-8,8:w-8]=cv2.GC_PR_BGD
rect=(max(5,int(w*.10)),max(5,int(h*.03)),int(w*.80),int(h*.94))
bgd=np.zeros((1,65),np.float64); fgd=np.zeros((1,65),np.float64)
cv2.grabCut(arr,gc,rect,bgd,fgd,5,cv2.GC_INIT_WITH_RECT)
hand=np.where((gc==cv2.GC_FGD)|(gc==cv2.GC_PR_FGD),255,0).astype(np.uint8)
hand=cv2.morphologyEx(hand,cv2.MORPH_CLOSE,np.ones((9,9),np.uint8),iterations=2)
hsv=cv2.cvtColor(arr,cv2.COLOR_RGB2HSV)
ink=cv2.bitwise_or(cv2.inRange(hsv,np.array([80,35,25]),np.array([145,255,245])),cv2.inRange(hsv,np.array([0,0,0]),np.array([179,255,90])))
ink=cv2.bitwise_and(cv2.dilate(ink,np.ones((7,7),np.uint8)),hand)
Image.fromarray(ink).save(WORK/"paint_mask.png")
controller=PowerPaintController(torch.float16,str(weights),True,"ppt-v1")
def pred(base,mask,prompt,negative,fitting,steps,scale,seed,task):
    d={"image":base.copy(),"mask":mask.copy()}
    r,_=controller.predict(d,prompt,fitting,steps,scale,seed,negative,task,None,None)
    return r[0].convert("RGB")
clean=pred(img,Image.fromarray(ink).convert("RGB"),"natural real human skin, realistic palm skin texture, empty clean hand, no drawing, no writing, no symbols","tattoo, henna, mehndi, text, letters, signature, blue ink, artwork, landscape, temple, mountain, extra fingers, deformed hand",.70,20,9.0,101,"object-removal")
clean.save(CLEAN)
inner=cv2.erode(hand,np.ones((25,25),np.uint8),iterations=1); Image.fromarray(inner).save(WORK/"art_mask.png")
prompt="""Real adult human hand, exact anatomy preserved, palm-up. Draw premium devotional Palm Art directly on real skin using ONLY blue/indigo BALLPOINT PEN. Thousands of thin imperfect biro strokes, fine outlines, hatching, cross-hatching, contour lines and stippling following palm creases. EXACT CENTER: LARGE unmistakable Lord Shiva/Mahadev, MAIN SUBJECT, 35-45% of palm, recognizable face, calm eyes, third eye, jata, crescent moon, snake, shoulders, torso, meditation pose and trishul. Around him a dense connected miniature Hindu devotional world: Himalayan temple, bells, oil lamps, flowers, river/ghat, mountains, trees and tiny pilgrims. Continue fine blue pen linework on every visible finger. Preserve skin pores, fingerprints, creases and nails. Photorealistic macro editorial photograph, clean light background, 2-3 real blue/black ballpoint pens beside wrist. Physically drawn on skin, not printed. Complete hand from wrist through all five fingertips."""
negative="""tattoo, henna, mehndi, decal, sticker, printed glove, digital overlay, CGI, 3D render, vector, marker, paint, watercolor, oil paint, smooth digital illustration, plastic hand, synthetic hand, blank fingers, blue nails only, mountain-only landscape, generic landscape, cropped hand, cropped fingertips, extra fingers, missing fingers, fused fingers, malformed hand, duplicate hand, watermark, logo, readable text, letters, signature, name, typography, multicolored ink, solid blue fill"""
final=pred(clean,Image.fromarray(inner).convert("RGB"),prompt,negative,.58,26,8.2,2027,"text-guided")
final.save(OUT)
print("POWERPAINT_TEST_DONE",OUT,"GPU",torch.cuda.get_device_name(0) if torch.cuda.is_available() else "NONE")
