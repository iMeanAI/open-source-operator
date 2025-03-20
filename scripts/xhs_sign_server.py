import time
from flask import Flask, request, jsonify
from gevent.pywsgi import WSGIServer
from gevent import monkey
from playwright.sync_api import sync_playwright
import traceback

monkey.patch_all()

app = Flask(__name__)
playwright = None
browser_context = None
context_page = None
stealth_js_path = "./stealth.min.js"

def get_context_page(instance, stealth_js_path):
    try:
        chromium = instance.chromium
        browser = chromium.launch(headless=False)
        context = browser.new_context()
        context.add_init_script(path=stealth_js_path)
        page = context.new_page()
        return context, page
    except Exception as e:
        print(f"创建浏览器上下文失败: {str(e)}")
        return None, None

def reset_browser():
    global browser_context, context_page, playwright
    try:
        if context_page:
            context_page.close()
        if browser_context:
            browser_context.close()
        if playwright:
            playwright.stop()
        
        playwright = sync_playwright().start()
        browser_context, context_page = get_context_page(playwright, stealth_js_path)
        if context_page:
            context_page.goto("https://www.xiaohongshu.com")
            time.sleep(5)
            context_page.reload()
            time.sleep(1)
            print("浏览器重置成功")
            return True
    except Exception as e:
        print(f"重置浏览器失败: {str(e)}")
        traceback.print_exc()
        return False

def get_current_cookies():
    try:
        if browser_context:
            cookies = browser_context.cookies()
            print(f"here cookies:{cookies}")
            a1 = ""
            web_session = ""
            xsecappid = ""
            for cookie in cookies:
                if cookie["name"] == "a1":
                    a1 = cookie["value"]
                elif cookie["name"] == "web_session":
                    web_session = cookie["value"]
            return {"a1": a1, "web_session": web_session}
    except Exception as e:
        print(f"获取cookies失败: {str(e)}")
    return {"a1": "", "web_session": ""}

def sign(uri, data, a1, web_session):
    global context_page
    try:
        encrypt_params = context_page.evaluate("([url, data]) => window._webmsxyw(url, data)", [uri, data])
        return {
            "x-s": encrypt_params["X-s"],
            "x-t": str(encrypt_params["X-t"]),
            "success": True
        }
    except Exception as e:
        print(f"签名失败: {str(e)}")
        if "Execution context was destroyed" in str(e):
            if reset_browser():
                try:
                    encrypt_params = context_page.evaluate("([url, data]) => window._webmsxyw(url, data)", [uri, data])
                    return {
                        "x-s": encrypt_params["X-s"],
                        "x-t": str(encrypt_params["X-t"]),
                        "success": True
                    }
                except Exception as e2:
                    print(f"重试签名失败: {str(e2)}")
        return {"success": False, "error": str(e)}

@app.route("/sign", methods=["POST"])
def handle_sign():
    try:
        json_data = request.json
        uri = json_data["uri"]
        data = json_data["data"]
        a1 = json_data["a1"]
        web_session = json_data["web_session"]
        result = sign(uri, data, a1, web_session)
        if result["success"]:
            return jsonify({
                "x-s": result["x-s"],
                "x-t": result["x-t"]
            })
        else:
            return jsonify({"error": result["error"]}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/cookies", methods=["GET"])
def get_cookies():
    return jsonify(get_current_cookies())

@app.route("/reset", methods=["POST"])
def handle_reset():
    if reset_browser():
        return jsonify({"success": True, "cookies": get_current_cookies()})
    return jsonify({"success": False}), 500

# 初始化浏览器
print("正在启动 playwright")
reset_browser()

if __name__ == '__main__':
    # 使用 gevent 的 WSGI 服务器替代默认的开发服务器
    http_server = WSGIServer(('0.0.0.0', 5005), app)
    print("服务器启动在 http://0.0.0.0:5005")
    http_server.serve_forever()

