import gradio as gr
import subprocess
import os
import uuid
import requests
import json
from datetime import datetime

OUTPUT_DIR = "output"
UPLOAD_DIR = "uploads"
CONFIG_FILE = "user_config.json"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

MODEL_PRESETS = {
    "OpenAI": {
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "default_model": "gpt-4o"
    },
    "DeepSeek": {
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "",
        "default_model": "deepseek-chat"
    },
    "OpenAI Compatible": {
        "base_url": "https://api.gitcode.com/api/v5",
        "api_key": "",
        "default_model": "deepseek-ai/DeepSeek-V3.2-Exp"
    },
    "Ollama (本地模型)": {
        "base_url": "http://localhost:11434/v1",
        "api_key": "a",
        "default_model": "llama3"
    }
}

def load_user_config():
    """加载用户配置"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"加载配置失败: {e}")
    return {}

def save_user_config(config):
    """保存用户配置"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return "配置已保存 ✅"
    except Exception as e:
        return f"保存配置失败: {e}"

def save_current_settings(provider, api_key, base_url, model_name, lang_in, lang_out, 
                         dual_output, no_watermark, skip_clean, rich_text_disable, 
                         enhance, max_pages, min_length):
    """保存当前设置"""
    config = {
        "provider": provider,
        "api_key": api_key,
        "base_url": base_url,
        "model_name": model_name,
        "lang_in": lang_in,
        "lang_out": lang_out,
        "dual_output": dual_output,
        "no_watermark": no_watermark,
        "skip_clean": skip_clean,
        "rich_text_disable": rich_text_disable,
        "enhance": enhance,
        "max_pages": max_pages,
        "min_length": min_length
    }
    return save_user_config(config)

def run_babeldoc_translation(input_path, output_path, model_name, base_url, api_key, lang_in, lang_out,
                             dual_output, no_watermark, skip_clean, rich_text_disable,
                             enhance, max_pages, min_length):
    # Check for None values and provide defaults
    if not model_name:
        model_name = "gpt-4o"  # Default model
    if not base_url:
        base_url = "https://api.openai.com/v1"
    if not api_key:
        api_key = ""
    
    command = [
        "babeldoc",
        "--files", input_path,
        "--openai",
        "--openai-model", model_name,
        "--openai-base-url", base_url,
        "--openai-api-key", api_key,
        "--lang-in", lang_in,
        "--lang-out", lang_out,
        "--output", output_path
    ]

    if not dual_output:
        command.append("--no-dual")
    if no_watermark:
        command.extend(["--watermark-output-mode", "no_watermark"])
    if skip_clean:
        command.append("--skip-clean")
    if rich_text_disable:
        command.append("--disable-rich-text-translate")
    if enhance:
        command.append("--enhance-compatibility")
    if max_pages:
        command.extend(["--max-pages-per-part", str(max_pages)])
    if min_length:
        command.extend(["--min-text-length", str(min_length)])

    print("📦 执行命令：", " ".join(command))

    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        return f"翻译出错：{str(e)}", None

    pdf_files = sorted(
        [f for f in os.listdir(output_path) if f.endswith(".pdf")],
        key=lambda x: os.path.getmtime(os.path.join(output_path, x)),
        reverse=True
    )
    if not pdf_files:
        return "翻译失败：未生成输出文件", None

    translated_path = os.path.join(output_path, pdf_files[0])
    return "翻译完成 ✅，点击下方链接下载：", translated_path

def get_ollama_models():
    try:
        response = requests.get("http://localhost:11434/api/tags")
        if response.status_code == 200:
            tags = response.json().get("models", [])
            return [tag["name"] for tag in tags]
    except Exception:
        pass
    return ["llama3"]

def get_openai_models(api_key, base_url):
    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.get(f"{base_url}/models", headers=headers, timeout=5)
        if response.status_code == 200:
            models = response.json().get("data", [])
            return [m["id"] for m in models]
    except Exception:
        pass
    return []



def translate_pdf(pdf_file, provider, api_key, base_url, model_name,
                  lang_in, lang_out, dual_output, no_watermark,
                  skip_clean, rich_text_disable, enhance, max_pages, min_length):
    if not pdf_file:
        return "请上传 PDF 文件", None
    
    # Validate required parameters
    if not model_name:
        return "请选择模型名称", None
    if provider != "Ollama (本地模型)" and not api_key:
        return "请输入 API Key", None
    if provider == "OpenAI Compatible" and not base_url:
        return "请输入 API Base URL", None

    upload_pdfs = sorted(
        [f for f in os.listdir(UPLOAD_DIR) if f.endswith(".pdf")],
        key=lambda x: os.path.getmtime(os.path.join(UPLOAD_DIR, x)),
        reverse=True
    )
    for old_file in upload_pdfs[30:]:
        try:
            os.remove(os.path.join(UPLOAD_DIR, old_file))
        except Exception as e:
            print(f"⚠️ 无法删除旧上传文件：{old_file}，原因：{e}")

    file_id = str(uuid.uuid4())
    filename = os.path.basename(pdf_file)
    name_root = os.path.splitext(filename)[0]
    input_path = os.path.join(UPLOAD_DIR, f"{file_id}_{filename}")
    with open(pdf_file, "rb") as src, open(input_path, "wb") as dst:
        dst.write(src.read())

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_subdir = os.path.join(OUTPUT_DIR, f"{name_root}_{timestamp}")
    os.makedirs(output_subdir, exist_ok=True)

    print("⚙️ 实际输入文件路径：", input_path)
    return run_babeldoc_translation(
        input_path, output_subdir, model_name, base_url, api_key,
        lang_in, lang_out, dual_output, no_watermark,
        skip_clean, rich_text_disable, enhance, max_pages, min_length
    )

def update_provider(provider):
    preset = MODEL_PRESETS[provider]
    default_model = preset["default_model"]
    if provider == "Ollama (本地模型)":
        models = get_ollama_models()
        default = models[0] if models else "llama3"
        return preset["api_key"], preset["base_url"], default
    else:
        return preset["api_key"], preset["base_url"], default_model



def load_saved_settings():
    """加载保存的设置"""
    config = load_user_config()
    if not config:
        return ("OpenAI", "", "https://api.openai.com/v1", "gpt-4o", "en", "zh", 
                True, True, True, True, True, "1", "5")
    
    return (
        config.get("provider", "OpenAI"),
        config.get("api_key", ""),
        config.get("base_url", "https://api.openai.com/v1"),
        config.get("model_name", "gpt-4o"),
        config.get("lang_in", "en"),
        config.get("lang_out", "zh"),
        config.get("dual_output", True),
        config.get("no_watermark", True),
        config.get("skip_clean", True),
        config.get("rich_text_disable", True),
        config.get("enhance", True),
        config.get("max_pages", "1"),
        config.get("min_length", "5")
    )

def refresh_models(api_key, base_url):
    models = get_openai_models(api_key, base_url)
    if not models:
        return "获取失败 ❌"
    return models[0] if models else ""

# 在创建界面前加载保存的设置
saved_settings = load_saved_settings()

with gr.Blocks() as demo:
    gr.Markdown("# 📄 BabelDOC - 多模型 PDF 翻译工具")

    gr.Markdown(
        '''
## 📘 小杜提醒您（README）

1. 上传你想翻译的 PDF 文件（目前仅支持 `.pdf`）。
2. 选择你要使用的模型：
   - **OpenAI**: 官方 OpenAI API
   - **DeepSeek**: DeepSeek API
   - **OpenAI Compatible**: 兼容 OpenAI API 的服务（如 GitCode、通义千问等）
   - **Ollama**: 本地模型
3. 输入对应的 API Key 和 Base URL（OpenAI Compatible 需要自定义）。
4. 选择源语言和目标语言（如英文 → 中文）。
5. 💾 **保存设置**: 点击"保存当前设置"可保存配置，下次打开自动加载。
6. 根据需要勾选选项：
   - ✅ 输出双语：原文+译文并排显示。
   - ✅ 无水印：去除“由 BabelDOC 生成”标识。
   - ✅ 跳过清洗：保留原始排版，不对 PDF 格式做清理。
   - ✅ 禁用富文本：避免保留加粗、超链接等格式。
7. 点击 🚀 开始翻译，稍等片刻后即可下载翻译结果。
8. 翻译文件将自动保存在 `output/原文件名_时间戳/` 目录下。

📢 欢迎关注小杜的X：
https://x.com/xiaodus

📂 **OpenAI Compatible 示例**:
- GitCode: Base URL 填写 `https://api.gitcode.com/api/v5` (不要包含 /chat/completions)
- 通义千问: Base URL 填写 `https://dashscope.aliyuncs.com/compatible-mode/v1`
- 注意：babeldoc 会自动在 Base URL 后添加 /chat/completions

📂 本地模型用户请确保 `Ollama` 服务器已运行，并加载模型（如 llama3、gemma 等）。
'''
    )

    with gr.Row():
        pdf_file = gr.File(label="上传 PDF 文件", file_types=[".pdf"], type="filepath")

    with gr.Row():
        provider = gr.Radio(
            label="选择翻译模型来源",
            choices=list(MODEL_PRESETS.keys()),
            value=saved_settings[0]
        )

    with gr.Row():
        api_key = gr.Text(label="API Key", type="password", value=saved_settings[1])
        base_url = gr.Text(label="API Base URL", value=saved_settings[2])
        model_name = gr.Textbox(label="模型名称", value=saved_settings[3], interactive=True)
        refresh_btn = gr.Button("🔄 刷新模型列表")

    with gr.Row():
        lang_in = gr.Dropdown(label="源语言", choices=["en", "zh", "ja"], value=saved_settings[4])
        lang_out = gr.Dropdown(label="目标语言", choices=["zh", "en", "ja"], value=saved_settings[5])
    
    with gr.Row():
        save_btn = gr.Button("💾 保存当前设置")
        save_status = gr.Textbox(label="保存状态", interactive=False, visible=False)

    with gr.Row():
        dual_output = gr.Checkbox(label="输出双语 PDF", value=saved_settings[6])
        no_watermark = gr.Checkbox(label="无水印输出", value=saved_settings[7])
        skip_clean = gr.Checkbox(label="跳过 PDF 清洗 (skip-clean)", value=saved_settings[8])
        rich_text_disable = gr.Checkbox(label="禁用富文本翻译 (disable-rich-text-translate)", value=saved_settings[9])
        enhance = gr.Checkbox(label="增强兼容性 (enhance-compatibility)", value=saved_settings[10])
        max_pages = gr.Textbox(label="最大分块页数 (max-pages-per-part)", value=saved_settings[11])
        min_length = gr.Textbox(label="最小翻译长度 (min-text-length)", value=saved_settings[12])

    run_button = gr.Button("🚀 开始翻译")
    status = gr.Textbox(label="状态", interactive=False)
    result_pdf = gr.File(label="翻译结果下载")



    provider.change(fn=update_provider, inputs=provider,
                    outputs=[api_key, base_url, model_name])

    refresh_btn.click(fn=refresh_models,
                      inputs=[api_key, base_url],
                      outputs=model_name)

    def save_and_show_status(*args):
        result = save_current_settings(*args)
        return gr.update(visible=True, value=result)
    
    save_btn.click(
        fn=save_and_show_status,
        inputs=[provider, api_key, base_url, model_name, lang_in, lang_out,
                dual_output, no_watermark, skip_clean, rich_text_disable, 
                enhance, max_pages, min_length],
        outputs=save_status
    )



    run_button.click(
        fn=translate_pdf,
        inputs=[pdf_file, provider, api_key, base_url, model_name,
                lang_in, lang_out, dual_output, no_watermark,
                skip_clean, rich_text_disable, enhance, max_pages, min_length],
        outputs=[status, result_pdf]
    )

if __name__ == "__main__":
    demo.launch()
