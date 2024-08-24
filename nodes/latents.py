import os
import torch
import requests
import safetensors.torch
import numpy as np
import io
from io import BytesIO
import json
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance
from PIL.PngImagePlugin import PngInfo
import folder_paths
import base64



class LoadLatentNumpy:
	def __init__(self):
		pass

	@classmethod
	def INPUT_TYPES(s):
		exts = [".latent", ".safetensors", ".npy", ".npz"]
		input_dir = folder_paths.get_input_directory()
		files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
		files = [f for f in files if any([f.endswith(x) for x in exts])]
		return {
			"required": {
				"latent": [sorted(files), ]
			},
		}

	RETURN_TYPES = ("LATENT",)
	FUNCTION = "load"
	CATEGORY = "remote/latent"
	TITLE = "Load Latent (Numpy)"

	def load_comfy(self, file):
		# From default node - renamed safetensors file
		if type(file) == str:
			data = safetensors.torch.load_file(file)
		else:
			data = safetensors.torch.load(file)

		latent = data["latent_tensor"].to(torch.float32)
		if "latent_format_version_0" not in data:
			latent *= 1.0 / 0.18215 # XL?
		return latent

	def load_numpy(self, file):
		# plain npy file - saved as-is
		return torch.from_numpy(np.load(file))

	def load_koyha(self, file):
		# generated by sd_scripts - npz
		if "latents" in data.keys():
			latent = data["latents"]
		else:
			latent = [x for x in data.items() if x.shape > 3][0]
		return torch.from_numpy(latent)

	def load(self, latent):
		path = folder_paths.get_annotated_filepath(latent)
		name, ext = os.path.splitext(latent)

		if ext in [".latent", ".safetensors"]:
			latent = self.load_comfy(path)
		elif ext == ".npy":
			latent = self.load_numpy(path)
		elif ext == ".npz":
			latent = self.load_koyha(path)
		else:
			try:
				latent = self.load_numpy(path)
			except:
				raise ValueError(f"Unknown latent extension '{ext}'")

		if len(latent.shape) == 3:
			latent = latent.unsqueeze(0)
		print("asdasd", latent.shape)

		return ({"samples": latent.to(torch.float32)},)

	@classmethod
	def IS_CHANGED(s, latent):
		image_path = folder_paths.get_annotated_filepath(latent)
		m = hashlib.sha256()
		with open(image_path, 'rb') as f:
			m.update(f.read())
		return m.digest().hex()

	@classmethod
	def VALIDATE_INPUTS(s, latent):
		if not folder_paths.exists_annotated_filepath(latent):
			return f"Invalid latent file '{latent}'"
		return True

class LoadLatentUrl(LoadLatentNumpy):
	def __init__(self):
		pass

	@classmethod
	def INPUT_TYPES(s):
		return {
			"required": {
				"url": ("STRING", { "multiline": False, })
			}
		}

	RETURN_TYPES = ("LATENT",)
	TITLE = "Load Latent (URL)"

	def load(self, url):
		buffer = BytesIO()
		with requests.get(url, stream=True, timeout=16) as r:
			r.raise_for_status()
			buffer.write(r.content)
		buffer.seek(0)

		if ".latent" in url or ".safetensors" in url:
			latent = self.load_comfy(buffer)
		elif ".npy" in url:
			latent = self.load_numpy(buffer)
		elif ".npz" in url:
			latent = self.load_koyha(buffer)
		else:
			try:
				latent = self.load_comfy(buffer)
			except:
				raise ValueError(f"Unknown latent extension '{url}'")

		if len(latent.shape) == 3:
			latent = latent.unsqueeze(0)

		del buffer
		return ({"samples": latent.to(torch.float32)},)

	@classmethod
	def IS_CHANGED(s, url):
		return str(url)

	@classmethod
	def VALIDATE_INPUTS(s, url):
		return True

class SaveLatentNumpy:
	def __init__(self):
		self.output_dir = folder_paths.get_output_directory()

	@classmethod
	def INPUT_TYPES(s):
		return {
			"required": {
				"samples": ("LATENT",),
				"filename_prefix": ("STRING", {"default": "latents/ComfyUI"})
			}
		}

	RETURN_TYPES = ("STRING",)
	RETURN_NAMES = ("filename",)
	OUTPUT_NODE = True
	FUNCTION = "save"
	CATEGORY = "remote/latent"
	TITLE = "Save Latent (Numpy)"

	def save(self, samples, filename_prefix="ComfyUI"):
		full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(filename_prefix, self.output_dir)
		fname = f"{filename}_{counter:05}_.npy"
		path = os.path.join(full_output_folder, fname)
		np.save(path, samples["samples"].numpy())
		return (fname,)


class LatentToBase64Nux:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "samples": ("LATENT",),
            }
        }
    
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("base64_latent",)
    FUNCTION = "convert"
    CATEGORY = "remote/latent"
    TITLE = "Latent to Base64"

    def convert(self, samples):
        # Convert the latent samples to a numpy array
        latent_array = samples["samples"].numpy()
        
        # Save the numpy array to a bytes buffer
        buffer = io.BytesIO()
        np.save(buffer, latent_array)
        buffer.seek(0)
        
        # Encode the bytes to base64
        base64_latent = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return (base64_latent,)
	

class LoadLatentFromBase64Nux:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "base64_latent": ("STRING", {"multiline": True, "default": "", "forceInput": True}, ),
            },
        }

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "load"
    CATEGORY = "remote/latent"
    TITLE = "Load Latent from Base64"

    def load(self, base64_latent=""):
        try:
            # Decode the base64 string
            decoded_data = base64.b64decode(base64_latent)
            
            # Load the numpy array from the decoded data
            buffer = io.BytesIO(decoded_data)
            latent_array = np.load(buffer)
            
            # Convert numpy array to torch tensor
            latent_tensor = torch.from_numpy(latent_array).to(torch.float32)
            
            # Ensure the tensor has the correct shape (add batch dimension if necessary)
            if len(latent_tensor.shape) == 3:
                latent_tensor = latent_tensor.unsqueeze(0)
            
            print("Loaded latent shape:", latent_tensor.shape)
            
            return ({"samples": latent_tensor},)
        
        except Exception as e:
            raise ValueError(f"Failed to load latent from base64: {str(e)}")

    @classmethod
    def IS_CHANGED(s, base64_latent):
        # Since the input is a string, we can use its hash as a change indicator
        return hash(base64_latent)

    @classmethod
    def VALIDATE_INPUTS(s, base64_latent):
        if not base64_latent:
            return "Base64 latent string is empty"
        try:
            decoded_data = base64.b64decode(base64_latent)
            buffer = io.BytesIO(decoded_data)
            np.load(buffer)
        except:
            return "Invalid base64 latent string"
        return True



class ConditioningToBase64:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "conditioning": ("CONDITIONING", {"tooltip": "The conditioning to be encoded as base64."}),
            }
        }
    
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("base64_conditioning",)
    FUNCTION = "convert"
    CATEGORY = "conditioning"
    TITLE = "Conditioning2Base64"

    def convert(self, conditioning):
        # Extract the conditioning data
        cond_data, cond_meta = conditioning[0]
        
        # Convert tensors to numpy arrays
        cond_data_np = cond_data.cpu().numpy()
        cond_meta_serializable = {k: v.cpu().numpy() if isinstance(v, torch.Tensor) else v for k, v in cond_meta.items()}
        
        # Combine data and metadata into a single dictionary
        combined_data = {
            "cond_data": cond_data_np,
            "cond_meta": cond_meta_serializable
        }
        
        # Save the combined data to a bytes buffer
        buffer = io.BytesIO()
        np.savez_compressed(buffer, **combined_data)
        buffer.seek(0)
        
        # Encode the bytes to base64
        base64_conditioning = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return (base64_conditioning,)

class ConditioningFromBase64:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "base64_conditioning": ("STRING", {"multiline": True, "forceInput": True}),
            }
        }
    
    RETURN_TYPES = ("CONDITIONING",)
    FUNCTION = "convert"
    CATEGORY = "conditioning"
    TITLE = "Remote Conditioning"

    def convert(self, base64_conditioning):
        try:
            # Decode the base64 string
            decoded_data = base64.b64decode(base64_conditioning)
            
            # Load the numpy arrays from the decoded data
            buffer = io.BytesIO(decoded_data)
            loaded_data = np.load(buffer, allow_pickle=True)
            
            # Extract the conditioning data and metadata
            cond_data_np = loaded_data['cond_data']
            cond_meta_serializable = loaded_data['cond_meta'].item()
            
            # Convert numpy arrays back to tensors
            cond_data = torch.from_numpy(cond_data_np)
            cond_meta = {k: torch.from_numpy(v) if isinstance(v, np.ndarray) else v for k, v in cond_meta_serializable.items()}
            
            # Reconstruct the conditioning object
            conditioning = [[cond_data, cond_meta]]
            
            return (conditioning,)
        
        except Exception as e:
            raise ValueError(f"Failed to load conditioning from base64: {str(e)}")

def align_text(align, img_height, text_height, text_pos_y, margins):
    if align == "center":
        text_plot_y = img_height / 2 - text_height / 2 + text_pos_y
    elif align == "top":
        text_plot_y = text_pos_y + margins                       
    elif align == "bottom":
        text_plot_y = img_height - text_height + text_pos_y - margins 
    return text_plot_y        


def justify_text(justify, img_width, line_width, margins):
    if justify == "left":
        text_plot_x = 0 + margins
    elif justify == "right":
        text_plot_x = img_width - line_width - margins
    elif justify == "center":
        text_plot_x = img_width/2 - line_width/2
    return text_plot_x   


def get_text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)

    # Calculate the text width and height
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    return text_width, text_height

def draw_masked_text(text_mask, text,
                     font_name, font_size,
                     margins, line_spacing,
                     position_x, position_y, 
                     align, justify,
                     rotation_angle, rotation_options):
    
    # Create the drawing context        
    draw = ImageDraw.Draw(text_mask)

    # Define font settings
    font_folder = "fonts"
    font_file = os.path.join(font_folder, font_name)
    resolved_font_path = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), font_file)
    font = ImageFont.truetype(str(resolved_font_path), size=font_size) 

     # Split the input text into lines
    text_lines = text.split('\n')

    # Calculate the size of the text plus padding for the tallest line
    max_text_width = 0
    max_text_height = 0

    for line in text_lines:
        # Calculate the width and height of the current line
        line_width, line_height = get_text_size(draw, line, font)
 
        line_height = line_height + line_spacing
        max_text_width = max(max_text_width, line_width)
        max_text_height = max(max_text_height, line_height)
    
    # Get the image width and height
    image_width, image_height = text_mask.size
    image_center_x = image_width / 2
    image_center_y = image_height / 2

    text_pos_y = position_y
    sum_text_plot_y = 0
    text_height = max_text_height * len(text_lines)

    for line in text_lines:
        # Calculate the width of the current line
        line_width, _ = get_text_size(draw, line, font)
                            
        # Get the text x and y positions for each line                                     
        text_plot_x = position_x + justify_text(justify, image_width, line_width, margins)
        text_plot_y = align_text(align, image_height, text_height, text_pos_y, margins)
        
        # Add the current line to the text mask
        draw.text((text_plot_x, text_plot_y), line, fill=255, font=font)
        
        text_pos_y += max_text_height  # Move down for the next line
        sum_text_plot_y += text_plot_y     # Sum the y positions

    # Calculate centers for rotation
    text_center_x = text_plot_x + max_text_width / 2
    text_center_y = sum_text_plot_y / len(text_lines)

    if rotation_options == "text center":
        rotated_text_mask = text_mask.rotate(rotation_angle, center=(text_center_x, text_center_y))
    elif rotation_options == "image center":    
        rotated_text_mask = text_mask.rotate(rotation_angle, center=(image_center_x, image_center_y))
        
    return rotated_text_mask        


class SaveImageWithBase64:
	def __init__(self):
		self.output_dir = folder_paths.get_output_directory()
		self.type = "output"
		self.prefix_append = ""
		self.compress_level = 4

	@classmethod
	def INPUT_TYPES(s):
		return {
			"required": {
				"images": ("IMAGE", {"tooltip": "The images to save."}),
				"filename_prefix": ("STRING", {"default": "ComfyUI",})
			},
			"optional": {
				"workflowName": ("STRING", {"default": "",}),
				"latent": ("LATENT",),
				"positive_conditioning": ("CONDITIONING",),
				"negative_conditioning": ("CONDITIONING",)
			},
			"hidden": {
				"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"
			},
		}

	RETURN_TYPES = ()
	FUNCTION = "save_images"
	OUTPUT_NODE = True
	CATEGORY = "image"
	TITLE = "save conds and latents"

	def save_images(self, images, filename_prefix="ComfyUI", workflowName="", latent=None, positive_conditioning=None, negative_conditioning=None, prompt=None, extra_pnginfo=None):

		def convertconditioning(conditioning):
			cond_data, cond_meta = conditioning[0]
			# Convert tensors to numpy arrays
			cond_data_np = cond_data.cpu().numpy()
			cond_meta_serializable = {k: v.cpu().numpy() if isinstance(v, torch.Tensor) else v for k, v in cond_meta.items()}
			# Combine data and metadata into a single dictionary
			combined_data = {
				"cond_data": cond_data_np,
				"cond_meta": cond_meta_serializable
			}
			# Save the combined data to a bytes buffer
			buffer = io.BytesIO()
			np.savez_compressed(buffer, **combined_data)
			buffer.seek(0)
			# Encode the bytes to base64
			base64_conditioning = base64.b64encode(buffer.getvalue()).decode('utf-8')
			return base64_conditioning

		def convertlatent(samples):
			# Convert the latent samples to a numpy array
			latent_array = samples["samples"].numpy()
			# Save the numpy array to a bytes buffer
			buffer = io.BytesIO()
			np.save(buffer, latent_array)
			buffer.seek(0)
			# Encode the bytes to base64
			base64_latent = base64.b64encode(buffer.getvalue()).decode('utf-8')	
			return base64_latent
		
		filename_prefix += self.prefix_append
		full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(filename_prefix, self.output_dir, images[0].shape[1], images[0].shape[0])
		results = list()
		for (batch_number, image) in enumerate(images):
			i = 255. * image.cpu().numpy()
			img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))

			# Add text overlay if workflowName is not empty
			if workflowName:
				#credits to comfyroll for text overlay
				# Convert tensor images
				image_3d = images[0, :, :, :]
				# Create PIL images for the text and background layers and text mask
				back_image = tensor2pil(image_3d)
				text_image = Image.new('RGB', back_image.size, (255, 255, 255))
				text_mask = Image.new('L', back_image.size)
				
				# Draw the text on the text mask
				rotated_text_mask = draw_masked_text(text_mask, workflowName, "Roboto-Regular.ttf", 30,
													0, 0, 
													0, 0,
													'center', 'center',
													0, 'text center')

				# Composite the text image onto the background image using the rotated text mask       
				img = Image.composite(text_image, back_image, rotated_text_mask)  
			
			metadata = PngInfo()
			if prompt is not None:
				metadata.add_text("prompt", json.dumps(prompt))
			if extra_pnginfo is not None:
				for x in extra_pnginfo:
					metadata.add_text(x, json.dumps(extra_pnginfo[x]))
			if latent is not None:
				latent_base64 = convertlatent(latent)
				metadata.add_text("latent_base64", latent_base64)
			if positive_conditioning is not None:
				p_conditioning_base64 = convertconditioning(positive_conditioning)
				metadata.add_text("conditioning_base64", p_conditioning_base64)
			if negative_conditioning is not None:
				n_conditioning_base64 = convertconditioning(negative_conditioning)
				metadata.add_text("conditioning_base64", n_conditioning_base64)
			filename_with_batch_num = filename.replace("%batch_num%", str(batch_number))
			file = f"{filename_with_batch_num}_{counter:05}_.png"
			img.save(os.path.join(full_output_folder, file), pnginfo=metadata, compress_level=self.compress_level)
			results.append({
				"filename": file,
				"subfolder": subfolder,
				"type": self.type
			})
			counter += 1
		return { "ui": { "images": results } }


class ExtractBase64FromImageUpload:
    @classmethod
    def INPUT_TYPES(s):
        input_dir = folder_paths.get_input_directory()
        files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
        return {"required":
                    {"image": (sorted(files), {"image_upload": True})},
                }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("latent_base64", "conditioning_base64")
    FUNCTION = "extract"
    CATEGORY = "image"
    TITLE = "Extracts base64 encoded latent and conditioning data from an image's metadata."

    def extract(self, image):
        image_path = folder_paths.get_annotated_filepath(image)
        img = Image.open(image_path)
        
        latent_base64 = None
        conditioning_base64 = None

        if "latent_base64" in img.info:
            latent_base64 = img.info["latent_base64"]
        
        if "conditioning_base64" in img.info:
            conditioning_base64 = img.info["conditioning_base64"]

        return (latent_base64, conditioning_base64)

    @classmethod
    def IS_CHANGED(s, image):
        image_path = folder_paths.get_annotated_filepath(image)
        m = hashlib.sha256()
        with open(image_path, 'rb') as f:
            m.update(f.read())
        return m.digest().hex()

def tensor2pil(t_image: torch.Tensor)  -> Image:
    return Image.fromarray(np.clip(255.0 * t_image.cpu().numpy().squeeze(), 0, 255).astype(np.uint8))

class ExtractBase64FromImage:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {"image": ("IMAGE",)}}

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("latent_base64", "conditioning_base64")
    FUNCTION = "extract"
    CATEGORY = "image"
    TITLE = "Extracts base64 encoded latent and conditioning data from an image tensor's metadata."

    def extract(self, image):
        # Access the tensor directly
        tensor = image[0]
        
        latent_base64 = None
        conditioning_base64 = None

        # Retrieve metadata from the tensor
        if hasattr(tensor, 'metadata'):
            metadata = tensor.metadata
            print("Metadata keys:", list(metadata.keys()))  # Print the metadata keys
            latent_base64 = metadata.get("latent_base64", None)
            conditioning_base64 = metadata.get("conditioning_base64", None)

        return (latent_base64, conditioning_base64)

NODE_CLASS_MAPPINGS = {
	"LoadLatentFromBase64(Nux)": LoadLatentFromBase64Nux,
	"LatentToBase64(Nux)": LatentToBase64Nux,
	"LoadLatentNumpy": LoadLatentNumpy,
	"LoadLatentUrl": LoadLatentUrl,
	"SaveLatentNumpy": SaveLatentNumpy,
	"ConditioningToBase64(Nux)": ConditioningToBase64,  # New class
	"ConditioningFromBase64(Nux)": ConditioningFromBase64,
	"SaveImageWithBase64(Nux)": SaveImageWithBase64,
	"ExtractBase64FromImage(Nux)": ExtractBase64FromImage,
    "ExtractBase64FromImageUpload(Nux)": ExtractBase64FromImageUpload
}