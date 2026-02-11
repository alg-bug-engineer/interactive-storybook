"""火山 TTS 官方 API 服务（付费用户专享）"""
import asyncio
import logging
import uuid
import json
from pathlib import Path
from typing import Optional

import websockets

from app.config import get_settings

logger = logging.getLogger(__name__)

# TTS 音频存储路径
_BASE_DIR = Path(__file__).parent.parent.parent
VOLCANO_TTS_AUDIO_DIR = _BASE_DIR / "backend" / "data" / "audio" / "volcano_tts"
VOLCANO_TTS_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

logger.info(f"[火山TTS] 音频目录: {VOLCANO_TTS_AUDIO_DIR}")


# ========== 协议实现（基于 apis/tts/protocols.py）==========
from enum import IntEnum
from dataclasses import dataclass
import io
import struct


class MsgType(IntEnum):
    """消息类型"""

    FullClientRequest = 0b1
    AudioOnlyClient = 0b10
    AudioOnlyServer = 0b1011
    FrontEndResultServer = 0b1100
    Error = 0b1111


class MsgTypeFlagBits(IntEnum):
    """消息标志位"""

    NoSeq = 0
    PositiveSeq = 0b1
    NegativeSeq = 0b11


@dataclass
class Message:
    """简化的 WebSocket 消息"""

    type: MsgType = MsgType.FullClientRequest
    payload: bytes = b""
    sequence: int = 0

    def marshal(self) -> bytes:
        """序列化消息"""
        buffer = io.BytesIO()

        # 简化的协议头（4字节）
        header = [
            0x11,  # version=1, header_size=1 (4 bytes)
            (self.type << 4) | MsgTypeFlagBits.NoSeq,
            0x10,  # serialization=JSON, compression=None
            0x00,  # reserved
        ]
        buffer.write(bytes(header))

        # Payload 长度和内容
        buffer.write(struct.pack(">I", len(self.payload)))
        buffer.write(self.payload)

        return buffer.getvalue()

    @classmethod
    def from_bytes(cls, data: bytes) -> "Message":
        """反序列化消息"""
        if len(data) < 8:
            raise ValueError(f"数据太短: {len(data)} bytes")

        msg_type = MsgType(data[1] >> 4)

        # 跳过头部（4字节）
        payload_size = struct.unpack(">I", data[4:8])[0]
        payload = data[8 : 8 + payload_size] if payload_size > 0 else b""

        # 检查是否有 sequence（音频消息）
        sequence = 0
        if msg_type == MsgType.AudioOnlyServer and len(data) > 8 + payload_size:
            # sequence 在 payload 之前的 4 字节
            pass  # 简化处理，不解析 sequence

        return cls(type=msg_type, payload=payload, sequence=sequence)


async def _receive_message(websocket) -> Message:
    """接收 WebSocket 消息"""
    data = await websocket.recv()
    if isinstance(data, bytes):
        return Message.from_bytes(data)
    else:
        raise ValueError(f"意外的消息类型: {type(data)}")


async def _send_message(websocket, msg: Message) -> None:
    """发送 WebSocket 消息"""
    await websocket.send(msg.marshal())


# ========== TTS 生成逻辑 ==========


def get_cluster(voice: str) -> str:
    """根据音色类型返回集群名称"""
    if voice.startswith("S_"):
        return "volcano_icl"
    return "volcano_tts"


async def generate_tts_audio_volcano(
    text: str,
    output_path: str,
    voice_id: Optional[str] = None,
    rate: str = "+0%",
    max_retries: int = 3,
) -> str:
    """
    使用火山 TTS 官方 API 生成语音

    Args:
        text: 要转换的文本
        output_path: 输出文件路径
        voice_id: 音色ID（可选，默认使用配置中的音色）
        rate: 语速调整（暂不支持）
        max_retries: 最大重试次数

    Returns:
        生成的音频文件路径

    Raises:
        RuntimeError: TTS 生成失败
    """
    settings = get_settings()

    # 验证配置
    if not settings.volcano_tts_appid or not settings.volcano_tts_access_token:
        raise RuntimeError(
            "火山 TTS API 配置不完整，请检查 .env 文件中的 "
            "VOLCANO_TTS_APPID 和 VOLCANO_TTS_ACCESS_TOKEN"
        )

    # 使用配置中的音色或用户指定的音色
    voice_type = voice_id or settings.volcano_tts_voice_type
    cluster = get_cluster(voice_type)

    # 确保输出目录存在
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    logger.info(
        f"[火山TTS] 开始生成语音，音色: {voice_type}, 文本长度: {len(text)}"
    )

    last_error = None
    for attempt in range(max_retries):
        try:
            # 如果是重试，添加延迟
            if attempt > 0:
                delay = 2**attempt
                logger.info(f"[火山TTS] 等待 {delay}s 后重试...")
                await asyncio.sleep(delay)

            # 连接 WebSocket
            headers = {
                "Authorization": f"Bearer;{settings.volcano_tts_access_token}",
            }

            logger.info(
                f"[火山TTS] 连接中: {settings.volcano_tts_endpoint}"
            )

            async with websockets.connect(
                settings.volcano_tts_endpoint,
                additional_headers=headers,
                max_size=10 * 1024 * 1024,
            ) as websocket:
                logid = websocket.response_headers.get("x-tt-logid", "N/A")
                logger.info(f"[火山TTS] ✅ 已连接，Logid: {logid}")

                # 准备请求
                request = {
                    "app": {
                        "appid": settings.volcano_tts_appid,
                        "token": settings.volcano_tts_access_token,
                        "cluster": cluster,
                    },
                    "user": {
                        "uid": str(uuid.uuid4()),
                    },
                    "audio": {
                        "voice_type": voice_type,
                        "encoding": settings.volcano_tts_encoding,
                    },
                    "request": {
                        "reqid": str(uuid.uuid4()),
                        "text": text,
                        "operation": "submit",
                        "with_timestamp": "1",
                        "extra_param": json.dumps(
                            {"disable_markdown_filter": False}
                        ),
                    },
                }

                # 发送请求
                msg = Message(
                    type=MsgType.FullClientRequest,
                    payload=json.dumps(request).encode(),
                )
                await _send_message(websocket, msg)
                logger.info("[火山TTS] ✅ 请求已发送")

                # 接收音频数据
                audio_data = bytearray()
                while True:
                    msg = await _receive_message(websocket)

                    if msg.type == MsgType.FrontEndResultServer:
                        # 忽略前端结果
                        continue
                    elif msg.type == MsgType.AudioOnlyServer:
                        audio_data.extend(msg.payload)
                        # 检查是否为最后一条消息（简化：假设连续接收即可）
                        if len(msg.payload) == 0:
                            break
                    elif msg.type == MsgType.Error:
                        error_msg = msg.payload.decode("utf-8", "ignore")
                        raise RuntimeError(f"TTS 错误: {error_msg}")
                    else:
                        # 继续接收
                        pass

                    # 超时保护：如果收到音频数据但没有结束标记，继续尝试接收
                    if len(audio_data) > 0:
                        try:
                            msg = await asyncio.wait_for(
                                _receive_message(websocket), timeout=1.0
                            )
                        except asyncio.TimeoutError:
                            # 超时，认为接收完成
                            logger.info(
                                "[火山TTS] 接收超时，认为音频接收完成"
                            )
                            break

                # 检查音频数据
                if not audio_data:
                    raise RuntimeError("未接收到音频数据")

                # 保存音频文件
                with open(output_path, "wb") as f:
                    f.write(audio_data)

                file_size_kb = len(audio_data) / 1024
                logger.info(
                    f"[火山TTS] ✅ 音频生成成功: {output_path} ({file_size_kb:.1f}KB)"
                )

                return output_path

        except Exception as e:
            last_error = e
            logger.warning(
                f"[火山TTS] ⚠️ 生成失败 (尝试 {attempt + 1}/{max_retries}): {e}"
            )

            if attempt == max_retries - 1:
                logger.error(
                    f"[火山TTS] ❌ 所有重试均失败: {e}", exc_info=True
                )

    # 所有重试都失败
    raise RuntimeError(
        f"火山 TTS 生成失败（已重试 {max_retries} 次）: {str(last_error)}"
    )


def get_volcano_tts_audio_path(story_id: str, segment_index: int, voice_id: str) -> Path:
    """
    获取火山 TTS 音频文件路径

    Args:
        story_id: 故事 ID
        segment_index: 段落索引
        voice_id: 音色 ID

    Returns:
        音频文件路径
    """
    filename = f"{story_id}_{segment_index}_{voice_id}.mp3"
    return VOLCANO_TTS_AUDIO_DIR / filename
