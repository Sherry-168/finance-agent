import os
import json
import requests
import dashscope
from http import HTTPStatus
from dashscope.audio.asr import Transcription
from dotenv import load_dotenv


load_dotenv()
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")


def speech_to_text(audio_file_path):
    """
    接收本地音频文件路径（比如 .wav 或 .mp3），返回识别出的文本。
    后端同学直接传文件路径进来即可。
    """
    try:

        task_response = Transcription.async_call(
            model='paraformer-v2',
            file_urls=[audio_file_path]
        )


        transcribe_response = Transcription.wait(task=task_response.output.task_id)

        if transcribe_response.status_code != HTTPStatus.OK:
            return {"error": f"语音识别接口请求失败，状态码: {transcribe_response.status_code}"}

        # 提取结果链接
        output = json.loads(json.dumps(transcribe_response.output))
        results = output.get('results', [])
        if not results:
            return {"error": "没有获取到识别结果"}


        result_json = requests.get(results[0]['transcription_url']).json()
        transcripts = result_json.get('transcripts', [])
        if not transcripts:
            return {"error": "转写内容为空"}

        # 返回最终纯文本
        return transcripts[0].get('text')

    except Exception as e:
        return {"error": f"ASR 发生异常: {str(e)}"}


if __name__ == '__main__':

    print("正在测试 ASR 函数...")

    print("代码已就绪，请后端同学传入本地文件路径进行测试。")
