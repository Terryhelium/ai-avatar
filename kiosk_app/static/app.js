const transcript = document.getElementById("transcript");
const form = document.getElementById("chatForm");
const input = document.getElementById("questionInput");
const submitButton = document.getElementById("submitButton");
const recordButton = document.getElementById("recordButton");
const recordButtonLabel = document.getElementById("recordButtonLabel");
const recordStatusText = document.getElementById("recordStatusText");
const stopAudioButton = document.getElementById("stopAudioButton");
const statusText = document.getElementById("statusText");
const timingsText = document.getElementById("timingsText");
const sourceStatusText = document.getElementById("sourceStatusText");
const sourceChunks = document.getElementById("sourceChunks");
const answerPreview = document.getElementById("answerPreview");
const serviceGrid = document.getElementById("serviceGrid");
const signalToggle = document.getElementById("signalToggle");
const signalBody = document.getElementById("signalBody");
const messageTemplate = document.getElementById("messageTemplate");
const avatarVideo = document.getElementById("avatarVideo");
const avatarAudio = document.getElementById("avatarAudio");
const avatarOverlay = document.getElementById("avatarOverlay");
const avatarHint = document.getElementById("avatarHint");
const avatarConnectButton = document.getElementById("avatarConnectButton");
const avatarStatusText = document.getElementById("avatarStatusText");

const history = [];
const PREFER_LOCAL_AUDIO = true;
let currentAudio = null;
let peerConnection = null;
let avatarConnecting = false;
let isBusy = false;
let isRecording = false;
let remoteAudioReady = false;
let mediaStream = null;
let audioContext = null;
let sourceNode = null;
let processorNode = null;
let silentGainNode = null;
let recordChunks = [];
let recordSampleRate = 16000;

function renderMessage(role, content) {
  const node = messageTemplate.content.firstElementChild.cloneNode(true);
  node.classList.add(role);
  node.querySelector(".message-role").textContent = role === "user" ? "访客" : "接待助手";
  node.querySelector(".message-content").textContent = content;
  transcript.appendChild(node);
  transcript.scrollTop = transcript.scrollHeight;
}

function compactHistory() {
  while (history.length > 4) {
    history.shift();
  }
}

function stopAudio() {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.currentTime = 0;
    currentAudio = null;
  }
  if (avatarAudio?.srcObject) {
    avatarAudio.pause();
    avatarAudio.muted = true;
    for (const track of avatarAudio.srcObject.getAudioTracks()) {
      track.enabled = false;
    }
  }
  statusText.textContent = "已停止播报";
}

function enableRemoteAudio() {
  if (PREFER_LOCAL_AUDIO) {
    remoteAudioReady = false;
    if (avatarAudio) {
      avatarAudio.muted = true;
    }
    return;
  }
  if (!avatarAudio?.srcObject) {
    remoteAudioReady = false;
    return;
  }
  avatarAudio.muted = false;
  for (const track of avatarAudio.srcObject.getAudioTracks()) {
    track.enabled = true;
  }
  avatarAudio.play()
    .then(() => {
      remoteAudioReady = true;
    })
    .catch(() => {
      remoteAudioReady = false;
    });
}

function syncBusyState() {
  submitButton.disabled = isBusy;
  input.disabled = isBusy;
  recordButton.disabled = isBusy && !isRecording;
}

function setBusy(nextBusy, message = null) {
  isBusy = nextBusy;
  syncBusyState();
  if (message !== null) {
    statusText.textContent = message;
    return;
  }
  if (nextBusy) {
    statusText.textContent = "正在调用知识库与语音服务...";
    return;
  }
  if (statusText.textContent.startsWith("正在") || statusText.textContent.startsWith("录音中")) {
    statusText.textContent = "待命中";
  }
}

function updateTimings(timings) {
  const items = Object.entries(timings || {}).map(([name, ms]) => `${name} ${ms}ms`);
  timingsText.textContent = items.join(" / ");
}

function updateAnswerPreview(answer) {
  answerPreview.textContent = answer?.trim() || "待返回";
  answerPreview.scrollTop = 0;
}

function normalizeChunkContent(content) {
  return String(content || "")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/(p|div|tr|li|h[1-6])>/gi, "\n")
    .replace(/<td[^>]*>/gi, " | ")
    .replace(/<\/td>/gi, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .replace(/[ \t]{2,}/g, " ")
    .trim();
}

function updateSourcePanel(chunks, status, detail) {
  if (!Array.isArray(chunks) || !status) {
    sourceStatusText.textContent = "待查询";
    sourceStatusText.classList.remove("warn");
    sourceStatusText.classList.remove("error");
    sourceChunks.innerHTML = "";
    return;
  }

  const retrievalChunks = chunks;
  sourceChunks.innerHTML = "";
  sourceStatusText.classList.remove("warn");
  sourceStatusText.classList.remove("error");

  if (status === "error") {
    const suffix = detail ? ` ${String(detail).slice(0, 140)}` : "";
    sourceStatusText.textContent = `知识库检索失败，当前为模型直答，请谨慎使用。${suffix}`;
    sourceStatusText.classList.add("error");
    return;
  }

  if (status === "disabled") {
    sourceStatusText.textContent = "知识库未配置，当前为模型直答。";
    sourceStatusText.classList.add("warn");
    return;
  }

  if (retrievalChunks.length === 0) {
    sourceStatusText.textContent = "未命中知识库，当前为模型直答，请谨慎使用。";
    sourceStatusText.classList.add("warn");
    return;
  }

  sourceStatusText.textContent = `已命中知识库 ${retrievalChunks.length} 条，以下为参考片段。`;

  for (const chunk of retrievalChunks.slice(0, 2)) {
    const node = document.createElement("div");
    node.className = "source-chunk";
    const normalized = normalizeChunkContent(chunk.content);
    node.textContent = normalized.length > 420 ? `${normalized.slice(0, 420)}…` : normalized;
    sourceChunks.appendChild(node);
  }
}

function setAvatarState(text, hint, disabled = false) {
  avatarStatusText.textContent = text;
  if (avatarHint) {
    avatarHint.textContent = hint;
  }
  avatarConnectButton.disabled = disabled;
}

function setRecordState(label, hint, { active = false, disabled = false } = {}) {
  recordButtonLabel.textContent = label;
  recordStatusText.textContent = hint;
  recordButton.classList.toggle("is-recording", active);
  recordButton.disabled = disabled;
}

function attachRemoteTrack(event) {
  if (event.track.kind === "video") {
    avatarVideo.srcObject = event.streams[0];
    avatarOverlay.classList.add("is-hidden");
    avatarVideo.play().catch(() => {});
  }
  if (event.track.kind === "audio") {
    avatarAudio.srcObject = event.streams[0];
    remoteAudioReady = false;
    enableRemoteAudio();
  }
}

async function negotiateAvatar() {
  peerConnection.addTransceiver("video", { direction: "recvonly" });
  peerConnection.addTransceiver("audio", { direction: "recvonly" });

  const offer = await peerConnection.createOffer();
  await peerConnection.setLocalDescription(offer);

  await new Promise((resolve) => {
    if (peerConnection.iceGatheringState === "complete") {
      resolve();
      return;
    }
    const checkState = () => {
      if (peerConnection.iceGatheringState === "complete") {
        peerConnection.removeEventListener("icegatheringstatechange", checkState);
        resolve();
      }
    };
    peerConnection.addEventListener("icegatheringstatechange", checkState);
  });

  const response = await fetch("/api/metahuman/offer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      sdp: peerConnection.localDescription.sdp,
      type: peerConnection.localDescription.type,
    }),
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  const answer = await response.json();
  await peerConnection.setRemoteDescription(answer);
}

async function connectAvatar() {
  if (avatarConnecting || peerConnection) {
    return;
  }

  avatarConnecting = true;
  setAvatarState("连接中", "正在和数字人服务建立 WebRTC 连接。", true);

  try {
    peerConnection = new RTCPeerConnection({ sdpSemantics: "unified-plan" });
    peerConnection.addEventListener("track", attachRemoteTrack);
    peerConnection.addEventListener("connectionstatechange", () => {
      const state = peerConnection?.connectionState;
      if (state === "connected") {
        setAvatarState("已连接", "数字人视频已连通，回答会同步推送。", true);
        avatarOverlay.classList.add("is-hidden");
      } else if (state === "failed" || state === "disconnected" || state === "closed") {
        disconnectAvatar();
        setAvatarState("未连接", "数字人连接已断开，可重新连接。");
      }
    });

    await negotiateAvatar();
    setAvatarState("已连接", "数字人视频已连通，回答会同步推送。", true);
  } catch (error) {
    disconnectAvatar();
    setAvatarState("未连接", "数字人连接失败，请稍后重试。");
    statusText.textContent = `数字人连接失败: ${error.message}`;
  } finally {
    avatarConnecting = false;
  }
}

function disconnectAvatar() {
  if (peerConnection) {
    peerConnection.close();
    peerConnection = null;
  }
  remoteAudioReady = false;
  avatarVideo.srcObject = null;
  avatarAudio.srcObject = null;
  avatarAudio.muted = false;
  avatarOverlay.classList.remove("is-hidden");
}

function buildVoiceFilename() {
  return "recording.wav";
}

function releaseRecorder() {
  if (processorNode) {
    processorNode.disconnect();
    processorNode.onaudioprocess = null;
  }
  if (sourceNode) {
    sourceNode.disconnect();
  }
  if (silentGainNode) {
    silentGainNode.disconnect();
  }
  if (mediaStream) {
    for (const track of mediaStream.getTracks()) {
      track.stop();
    }
  }
  if (audioContext) {
    audioContext.close().catch(() => {});
  }
  processorNode = null;
  sourceNode = null;
  silentGainNode = null;
  mediaStream = null;
  audioContext = null;
  recordChunks = [];
}

async function loadHealth() {
  try {
    const response = await fetch("/api/health");
    const payload = await response.json();
    serviceGrid.innerHTML = "";
    for (const service of payload.services) {
      const card = document.createElement("div");
      card.className = `service-card ${service.ok ? "ok" : "down"}`;
      card.innerHTML = `<strong>${service.name}</strong><span>${service.detail}</span>`;
      serviceGrid.appendChild(card);
    }
  } catch (error) {
    serviceGrid.innerHTML = "";
    const card = document.createElement("div");
    card.className = "service-card down";
    card.innerHTML = "<strong>health</strong><span>加载失败</span>";
    serviceGrid.appendChild(card);
  }
}

async function sendQuestion(question) {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      history,
      synthesize_audio: true,
    }),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `HTTP ${response.status}`);
  }

  return response.json();
}

async function sendVoiceQuestion(audioBlob) {
  const formData = new FormData();
  formData.append("audio", audioBlob, buildVoiceFilename());
  formData.append("history", JSON.stringify(history));
  formData.append("synthesize_audio", "true");

  const response = await fetch("/api/voice-chat", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `HTTP ${response.status}`);
  }

  return response.json();
}

function handleAnswerPayload(question, payload) {
  renderMessage("user", question);
  history.push({ role: "user", content: question });
  compactHistory();

  renderMessage("assistant", payload.answer);
  history.push({ role: "assistant", content: payload.answer });
  compactHistory();

  updateAnswerPreview(payload.answer);
  updateTimings(payload.timings_ms);
  updateSourcePanel(payload.retrieval_chunks, payload.retrieval_status, payload.retrieval_detail);
  statusText.textContent = payload.audio_base64 ? "已完成并开始播报" : "已完成（未返回音频）";
  if (!payload.metahuman_dispatched && peerConnection) {
    statusText.textContent = "已完成并播报，数字人推送未成功";
  }

  const shouldPlayLocalAudio =
    payload.audio_base64
    && (
      PREFER_LOCAL_AUDIO
      || !(peerConnection && payload.metahuman_dispatched && remoteAudioReady)
    );
  if (shouldPlayLocalAudio) {
    currentAudio = new Audio(`data:${payload.audio_mime_type};base64,${payload.audio_base64}`);
    currentAudio.play().catch(() => {
      statusText.textContent = "回答已完成，浏览器阻止了自动播放";
    });
    return;
  }

  if (!PREFER_LOCAL_AUDIO && payload.audio_base64 && peerConnection && payload.metahuman_dispatched && remoteAudioReady) {
    enableRemoteAudio();
    statusText.textContent = "已完成，正在通过数字人播报";
    return;
  }

  if (!PREFER_LOCAL_AUDIO && payload.audio_base64 && peerConnection && payload.metahuman_dispatched && !remoteAudioReady) {
    statusText.textContent = "数字人音频未就绪，已回退本地播报";
  }

  if (PREFER_LOCAL_AUDIO && payload.audio_base64) {
    statusText.textContent = "已完成，正在本地播报";
  }
}

function mergeRecordChunks(chunks) {
  let totalLength = 0;
  for (const chunk of chunks) {
    totalLength += chunk.length;
  }

  const merged = new Float32Array(totalLength);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.length;
  }
  return merged;
}

function downsampleBuffer(buffer, inputSampleRate, outputSampleRate) {
  if (inputSampleRate === outputSampleRate) {
    return buffer;
  }

  const sampleRateRatio = inputSampleRate / outputSampleRate;
  const newLength = Math.round(buffer.length / sampleRateRatio);
  const result = new Float32Array(newLength);
  let offsetResult = 0;
  let offsetBuffer = 0;

  while (offsetResult < result.length) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * sampleRateRatio);
    let accum = 0;
    let count = 0;
    for (let index = offsetBuffer; index < nextOffsetBuffer && index < buffer.length; index += 1) {
      accum += buffer[index];
      count += 1;
    }
    result[offsetResult] = count > 0 ? accum / count : 0;
    offsetResult += 1;
    offsetBuffer = nextOffsetBuffer;
  }
  return result;
}

function writeWavString(view, offset, value) {
  for (let index = 0; index < value.length; index += 1) {
    view.setUint8(offset + index, value.charCodeAt(index));
  }
}

function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);

  writeWavString(view, 0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeWavString(view, 8, "WAVE");
  writeWavString(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeWavString(view, 36, "data");
  view.setUint32(40, samples.length * 2, true);

  let offset = 44;
  for (const sample of samples) {
    const value = Math.max(-1, Math.min(1, sample));
    view.setInt16(offset, value < 0 ? value * 0x8000 : value * 0x7fff, true);
    offset += 2;
  }
  return new Blob([buffer], { type: "audio/wav" });
}

async function handleRecordedAudio(chunks, sampleRate) {
  const mergedSamples = mergeRecordChunks(chunks);
  const downsampled = downsampleBuffer(mergedSamples, sampleRate, 16000);
  const audioBlob = encodeWav(downsampled, 16000);

  stopAudio();
  setBusy(true, "正在识别语音并调用知识库...");
  setRecordState("点击开始录音", "结束录音后自动送入 FunASR 和知识库问答", {
    disabled: true,
  });

  try {
    const payload = await sendVoiceQuestion(audioBlob);
    handleAnswerPayload(payload.transcript, payload);
  } catch (error) {
    renderMessage("assistant", "当前语音链路未返回结果，请检查浏览器录音、FunASR 和上游服务。");
    updateSourcePanel([]);
    statusText.textContent = `语音请求失败: ${error.message}`;
  } finally {
    setBusy(false);
    setRecordState("点击开始录音", "结束录音后自动送入 FunASR 和知识库问答");
  }
}

async function startRecording() {
  if (isBusy || isRecording) {
    return;
  }
  if (!window.isSecureContext) {
    statusText.textContent = "当前页面不是安全上下文，浏览器会拦截麦克风。请走 HTTPS 入口。";
    return;
  }
  const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextCtor || !navigator.mediaDevices?.getUserMedia) {
    statusText.textContent = "当前浏览器不支持录音，请改用文字输入。";
    return;
  }

  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioContext = new AudioContextCtor();
    recordSampleRate = audioContext.sampleRate;
    sourceNode = audioContext.createMediaStreamSource(mediaStream);
    processorNode = audioContext.createScriptProcessor(4096, 1, 1);
    silentGainNode = audioContext.createGain();
    silentGainNode.gain.value = 0;
    recordChunks = [];
    processorNode.onaudioprocess = (event) => {
      const samples = event.inputBuffer.getChannelData(0);
      recordChunks.push(new Float32Array(samples));
    };
    sourceNode.connect(processorNode);
    processorNode.connect(silentGainNode);
    silentGainNode.connect(audioContext.destination);
    isRecording = true;
    syncBusyState();
    timingsText.textContent = "";
    setRecordState("点击结束录音", "录音中，结束后自动识别并提问", { active: true });
    statusText.textContent = "录音中，请对着麦克风说话。";
  } catch (error) {
    releaseRecorder();
    setRecordState("点击开始录音", "结束录音后自动送入 FunASR 和知识库问答");
    const detail = error?.message || "浏览器拒绝了麦克风权限";
    statusText.textContent = `录音启动失败: ${detail}`;
  }
}

function stopRecording() {
  if (!processorNode || !isRecording) {
    return;
  }
  setRecordState("结束录音中", "正在整理音频并准备识别", { active: true, disabled: true });
  const chunks = recordChunks.map((chunk) => new Float32Array(chunk));
  const sampleRate = recordSampleRate;
  isRecording = false;
  releaseRecorder();
  handleRecordedAudio(chunks, sampleRate).catch((error) => {
    statusText.textContent = `录音处理失败: ${error.message}`;
    isRecording = false;
    releaseRecorder();
    setBusy(false);
    setRecordState("点击开始录音", "结束录音后自动送入 FunASR 和知识库问答");
  });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = input.value.trim();
  if (!question) {
    return;
  }

  stopAudio();
  input.value = "";
  setBusy(true);

  try {
    const payload = await sendQuestion(question);
    handleAnswerPayload(question, payload);
  } catch (error) {
    renderMessage("assistant", "当前服务未返回结果，请检查 RAGFlow / Ollama / CosyVoice 连通性。");
    updateSourcePanel([]);
    statusText.textContent = `请求失败: ${error.message}`;
  } finally {
    setBusy(false);
  }
});

stopAudioButton.addEventListener("click", stopAudio);
recordButton.addEventListener("click", () => {
  if (isRecording) {
    stopRecording();
    return;
  }
  startRecording().catch((error) => {
    statusText.textContent = `录音启动失败: ${error.message}`;
  });
});
avatarConnectButton.addEventListener("click", connectAvatar);
signalToggle.addEventListener("click", () => {
  signalBody.classList.toggle("is-open");
  signalToggle.textContent = signalBody.classList.contains("is-open") ? "关闭调试" : "调试";
});

renderMessage("assistant", "您好，这里是档案馆接待助手。您可以直接输入问题，我会基于现有知识库作答并播报。");
updateAnswerPreview("");
updateSourcePanel(null);
setAvatarState("未连接", "点击下方按钮建立数字人连接。");
setRecordState("点击开始录音", "结束录音后自动送入 FunASR 和知识库问答");
signalToggle.textContent = signalBody.classList.contains("is-open") ? "关闭调试" : "调试";
loadHealth();
