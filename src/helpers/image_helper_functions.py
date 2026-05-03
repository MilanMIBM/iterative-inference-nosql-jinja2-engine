import base64
import mimetypes
import tempfile
from io import BytesIO
from ibm_watsonx_ai.foundation_models import ModelInference
import os

# Try to import PIL and pillow_heif for HEIC support
try:
    from PIL import Image
    import pillow_heif

    HEIC_SUPPORT = True
except ImportError:
    HEIC_SUPPORT = False


def create_data_url(image_contents: bytes | str | os.PathLike, filename: str = None) -> str:
    """
    Convert image contents to a data URL format.

    Args:
        image_contents: The binary contents of the image file, or a filepath (str, Path, PosixPath, etc.) to read from
        filename: The filename used to determine the MIME type (inferred from filepath if not provided)

    Returns:
        A data URL string in the format 'data:mime_type;base64,encoded_data'
    """
    if isinstance(image_contents, (str, os.PathLike)):
        path = os.fspath(image_contents)
        if filename is None:
            filename = os.path.basename(path)
        with open(path, "rb") as f:
            image_contents = f.read()

    encoded_string = base64.b64encode(image_contents).decode("utf-8")

    mime_type, _ = mimetypes.guess_type(filename)
    if not mime_type:
        mime_type = "application/octet-stream"

    return f"data:{mime_type};base64,{encoded_string}"


def convert_heic_to_jpg(heic_contents: bytes) -> bytes:
    """
    Convert HEIC file contents to JPEG format.

    Args:
        heic_contents: HEIC file contents as bytes

    Returns:
        JPEG file contents as bytes
    """
    if not HEIC_SUPPORT:
        raise RuntimeError("HEIC support not available. Install pillow-heif package.")

    pillow_heif.register_heif_opener()

    # Write to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".heic") as temp_heic:
        temp_heic.write(heic_contents)
        temp_heic_path = temp_heic.name

    try:
        # Convert to JPEG
        with Image.open(temp_heic_path) as img:
            rgb_image = img.convert("RGB")

            # Save to BytesIO
            output = BytesIO()
            rgb_image.save(output, "JPEG", quality=95)
            output.seek(0)
            jpg_contents = output.read()

        return jpg_contents
    finally:
        # Clean up temp file
        if os.path.exists(temp_heic_path):
            os.unlink(temp_heic_path)


def extract_text_from_image(
    image_contents: bytes, filename: str, chat_model: ModelInference, system_prompt: str
) -> str:
    """
    Extract text from a single image using watsonx.ai vision model.

    Args:
        image_contents: Image file contents
        filename: Image filename
        chat_model: Initialized ModelInference instance
        system_prompt: System prompt for extraction

    Returns:
        Extracted text as markdown
    """
    image_data_url = create_data_url(image_contents, filename)

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Please extract the text from this image."},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ],
        },
    ]

    response = chat_model.chat(messages=messages)
    return response["choices"][0]["message"]["content"]


def create_image_example_message(instruction_prompt, file_example, output_text):
    """
    Create an example user message with image and corresponding assistant response.

    Args:
        instruction_prompt (str): The instruction prompt for processing images
        file_example: File uploader object or tuple from .value
        output_text (str): Expected output text for the example

    Returns:
        list: [user_message, assistant_message] pair for few-shot learning
    """
    if hasattr(file_example, "contents"):
        file_contents = file_example.contents()
        file_name = file_example.name()
    else:
        file_contents = file_example.contents(0)
        file_name = file_example.name(0)

    if file_name.lower().endswith(".heic"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".heic") as temp_heic:
            temp_heic.write(file_contents)
            temp_heic_path = temp_heic.name

        temp_jpg_path = convert_heic_to_jpg(temp_heic_path)

        with open(temp_jpg_path, "rb") as jpg_file:
            file_contents = jpg_file.read()

        file_name = file_name.rsplit(".", 1)[0] + ".jpg"
        os.unlink(temp_heic_path)
        os.unlink(temp_jpg_path)

    image_data_url = create_data_url(file_contents, file_name)

    user_message = {
        "role": "user",
        "content": [
            {"type": "text", "text": instruction_prompt},
            {
                "type": "image_url",
                "image_url": {"url": image_data_url},
            },
        ],
    }

    assistant_message = {"role": "assistant", "content": output_text}

    return [user_message, assistant_message]
