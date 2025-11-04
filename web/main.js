let recordBtn = document.getElementById('recordBtn');
let textInput = document.getElementById('textInput');
let sendTextBtn = document.getElementById('sendTextBtn');
let historyDiv = document.getElementById('history');
let player = document.getElementById('player');
let sessionId = null;

let mediaRecorder;
let chunks = [];
let isRecording = false;

function updateRecordButton(recording) {
  isRecording = recording;
  recordBtn.dataset.recording = recording;
  recordBtn.innerHTML = recording ?
    '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" /></svg> Stop' :
    '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" /></svg> Record';
}

recordBtn.onclick = async () => {
  if (isRecording) {
    mediaRecorder.stop();
    updateRecordButton(false);
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  mediaRecorder = new MediaRecorder(stream);
  mediaRecorder.ondataavailable = e => chunks.push(e.data);
  mediaRecorder.onstop = handleRecorded;
    mediaRecorder.start();
    updateRecordButton(true);
  } catch (err) {
    console.error('Microphone error', err);
    addHistory('system', 'Microphone access denied or not available');
  }
};

// Convert a recorded WebM/Opus blob to WAV (PCM 16-bit) so server/whisper handles it reliably.
async function webmToWav(webmBlob) {
  // Decode with AudioContext then encode to WAV
  const arrayBuffer = await webmBlob.arrayBuffer();
  const ac = new (window.AudioContext || window.webkitAudioContext)();
  const audioBuffer = await ac.decodeAudioData(arrayBuffer);

  // We'll use the first channel (mono) — resample to 16k or keep sampleRate if needed by server
  const sampleRate = 16000; // whisper works fine with 16k/32k; using 16k reduces size
  const channelData = audioBuffer.getChannelData(0);

  // resample
  const float32Data = (sampleRate === audioBuffer.sampleRate) ? channelData : resample(channelData, audioBuffer.sampleRate, sampleRate);

  // PCM16 encode
  const wavBuffer = encodeWAV(float32Data, sampleRate);
  return new Blob([wavBuffer], { type: 'audio/wav' });
}

function resample(buffer, srcRate, dstRate) {
  const ratio = srcRate / dstRate;
  const newLength = Math.round(buffer.length / ratio);
  const resampled = new Float32Array(newLength);
  for (let i = 0; i < newLength; i++) {
    const srcIndex = i * ratio;
    const i0 = Math.floor(srcIndex);
    const i1 = Math.min(i0 + 1, buffer.length - 1);
    const t = srcIndex - i0;
    resampled[i] = (1 - t) * buffer[i0] + t * buffer[i1];
  }
  return resampled;
}

function encodeWAV(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);

  /* RIFF identifier */ writeString(view, 0, 'RIFF');
  /* file length */ view.setUint32(4, 36 + samples.length * 2, true);
  /* RIFF type */ writeString(view, 8, 'WAVE');
  /* format chunk identifier */ writeString(view, 12, 'fmt ');
  /* format chunk length */ view.setUint32(16, 16, true);
  /* sample format (raw) */ view.setUint16(20, 1, true);
  /* channel count */ view.setUint16(22, 1, true);
  /* sample rate */ view.setUint32(24, sampleRate, true);
  /* byte rate (sampleRate * blockAlign) */ view.setUint32(28, sampleRate * 2, true);
  /* block align (channel count * bytes per sample) */ view.setUint16(32, 2, true);
  /* bits per sample */ view.setUint16(34, 16, true);
  /* data chunk identifier */ writeString(view, 36, 'data');
  /* data chunk length */ view.setUint32(40, samples.length * 2, true);

  // write the PCM samples
  floatTo16BitPCM(view, 44, samples);
  return view;
}

function floatTo16BitPCM(output, offset, input) {
  for (let i = 0; i < input.length; i++, offset += 2) {
    let s = Math.max(-1, Math.min(1, input[i]));
    s = s < 0 ? s * 0x8000 : s * 0x7fff;
    output.setInt16(offset, s, true);
  }
}

function writeString(view, offset, string) {
  for (let i = 0; i < string.length; i++) {
    view.setUint8(offset + i, string.charCodeAt(i));
  }
}

async function handleRecorded() {
  const webmBlob = new Blob(chunks, { type: 'audio/webm' });
  const byteSize = webmBlob.size;
  // keep chunks for conversion/upload; we'll clear after creating wav blob

    // recording captured (no preview shown per user preference)

  // compute client-side RMS/peak for debugging
  try {
    const arrayBuffer = await webmBlob.arrayBuffer();
    const ac = new (window.AudioContext || window.webkitAudioContext)();
    const audioBuffer = await ac.decodeAudioData(arrayBuffer);
    const channelData = audioBuffer.getChannelData(0);
    let sumSquares = 0;
    let peak = 0;
    for (let i = 0; i < channelData.length; i++) {
      const v = channelData[i];
      sumSquares += v * v;
      if (Math.abs(v) > peak) peak = Math.abs(v);
    }
    const rms = Math.sqrt(sumSquares / channelData.length);
    const maxAmp = 1.0;
    let rms_db = (rms <= 0) ? -Infinity : 20 * Math.log10(rms / maxAmp);
    // only show a user-visible warning when the recording is effectively silent
    if (!isFinite(rms_db) || rms_db < -60) {
      addHistory('system', '⚠️ Recording appears very quiet or silent. Check microphone permissions, input device, or increase microphone volume.');
    }
  } catch (e) {
    console.warn('Client-side audio analysis failed', e);
    addHistory('system', '⚠️ Could not analyze recorded audio on client (decode error)');
  }

  // proceed to convert and upload
  try {
    const wavBlob = await webmToWav(webmBlob);
    chunks = [];

    // create loading entry and keep reference
    const loadingElem = addHistory('user', '🎤 Processing voice message...');

    const fd = new FormData();
    fd.append('audio', wavBlob, 'recording.wav');

    const res = await fetch('/api/stt', { method: 'POST', body: fd });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    const data = await res.json();

    if (loadingElem && loadingElem.parentElement) loadingElem.parentElement.removeChild(loadingElem);

    const transcript = data && data.text ? data.text : '';
    if (!transcript || transcript.trim().length === 0) {
      addHistory('system', '⚠️ Transcription empty — try speaking more clearly or check ffmpeg availability on the server.');
    } else {
      await processMessage(transcript);
    }
  } catch (error) {
    console.error('STT upload error', error);
    addHistory('system', '❌ Failed to process voice message');
  }
}

async function processMessage(text) {
  addHistory('user', text);
  sendTextBtn.disabled = true;
  textInput.disabled = true;

  try {
    const chatRes = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, session_id: sessionId })
    });
    const chatData = await chatRes.json();
    sessionId = chatData.session_id;
    document.getElementById('sessionId').innerText = sessionId;

    addHistory('assistant', chatData.assistant);

    // fetch and play TTS
    const ttsResp = await fetch(`/api/tts?text=${encodeURIComponent(chatData.assistant)}`);
    const audioBlob = await ttsResp.blob();
    player.src = URL.createObjectURL(audioBlob);
    await player.play();
  } catch (error) {
    console.error('Chat error', error);
    addHistory('system', '❌ Failed to get response');
  } finally {
    sendTextBtn.disabled = false;
    textInput.disabled = false;
    textInput.focus();
  }
}

sendTextBtn.onclick = () => {
  const text = textInput.value.trim();
  if (!text) return;
  processMessage(text);
  textInput.value = '';
};

textInput.onkeypress = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendTextBtn.click();
  }
};

function addHistory(role, text) {
  const div = document.createElement('div');
  div.className = `message ${role}`;

  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  avatar.textContent = role === 'user' ? '👤' : (role === 'assistant' ? '🤖' : 'ℹ️');

  const content = document.createElement('div');
  content.className = 'content';
  content.textContent = text;

  if (role === 'user') {
    div.appendChild(content);
    div.appendChild(avatar);
  } else {
    div.appendChild(avatar);
    div.appendChild(content);
  }

  historyDiv.prepend(div);
  window.scrollTo(0, 0);
  return div;
}

// initial focus
textInput.focus();

