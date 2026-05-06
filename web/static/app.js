let sessionId = null;
let stream = null;
let recorder = null;
let chunks = [];
let isRecording = false;
let pendingAssistantText = null;
let recordingTimeoutId = null;

const MAX_RECORDING_MS = 60_000;

const startScreen = document.querySelector("#start-screen");
const callScreen = document.querySelector("#call-screen");
const startButton = document.querySelector("#start-button");
const resetButton = document.querySelector("#reset-button");
const recordButton = document.querySelector("#record-button");
const recordButtonLabel = document.querySelector("#record-button-label");
const statusEl = document.querySelector("#status");
const transcriptEl = document.querySelector("#transcript");
const audioEl = document.querySelector("#assistant-audio");
const debugOutput = document.querySelector("#debug-output");

function setStatus(value) {
  statusEl.textContent = value;
  statusEl.closest(".status-pill").dataset.state = value.toLowerCase();
}

function showStartScreen() {
  startScreen.classList.remove("hidden");
  callScreen.classList.add("hidden");
}

function showCallScreen() {
  startScreen.classList.add("hidden");
  callScreen.classList.remove("hidden");
}

function appendTurn(role, text) {
  if (!text) return;

  const item = document.createElement("div");
  item.className = `turn ${role}`;

  const label = document.createElement("span");
  label.className = "turn-label";
  label.textContent = role === "user" ? "You" : "Le Jardin";

  const copy = document.createElement("span");
  copy.textContent = text;

  item.append(label, copy);
  transcriptEl.appendChild(item);
  transcriptEl.scrollTop = transcriptEl.scrollHeight;
}

function preferredMimeType() {
  const options = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
  return options.find((type) => MediaRecorder.isTypeSupported(type)) || "";
}

function clearRecordingTimeout() {
  if (recordingTimeoutId) {
    clearTimeout(recordingTimeoutId);
    recordingTimeoutId = null;
  }
}

function stopRecording() {
  clearRecordingTimeout();

  if (recorder && recorder.state !== "inactive") {
    recorder.stop();
  }
}

async function playAssistant(audioUrl, text) {
  pendingAssistantText = text;
  recordButton.disabled = true;
  setStatus("Speaking");

  audioEl.src = `${audioUrl}?t=${Date.now()}`;

  try {
    await audioEl.play();
  } catch {
    appendTurn("assistant", text);
    pendingAssistantText = null;
    recordButton.disabled = false;
    setStatus("Ready");
  }
}

audioEl.addEventListener("ended", () => {
  if (pendingAssistantText) {
    appendTurn("assistant", pendingAssistantText);
  }

  pendingAssistantText = null;
  recordButton.disabled = false;
  setStatus("Ready");
});

startButton.addEventListener("click", async () => {
  startButton.disabled = true;
  showCallScreen();
  setStatus("Processing");

  try {
    const response = await fetch("/session/start", { method: "POST" });
    if (!response.ok) throw new Error(await response.text());

    const data = await response.json();

    sessionId = data.session_id;
    await playAssistant(data.audio_url, data.reply);
  } catch (error) {
    showStartScreen();
    startButton.disabled = false;
    console.error(error);
  }
});

resetButton.addEventListener("click", () => {
  window.location.reload();
});

recordButton.addEventListener("click", async () => {
  if (isRecording) {
    stopRecording();
    return;
  }

  try {
    stream ??= await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (error) {
    appendTurn("assistant", "Microphone access is needed to continue.");
    setStatus("Ready");
    console.error(error);
    return;
  }

  chunks = [];
  const mimeType = preferredMimeType();
  recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);

  recorder.addEventListener("dataavailable", (event) => {
    if (event.data.size > 0) chunks.push(event.data);
  });

  recorder.addEventListener("stop", sendRecording);

  recorder.start();
  recordingTimeoutId = setTimeout(stopRecording, MAX_RECORDING_MS);
  isRecording = true;
  recordButton.classList.add("recording");
  recordButtonLabel.textContent = "Stop and send";
  setStatus("Listening");
});

async function sendRecording() {
  clearRecordingTimeout();
  isRecording = false;
  recordButton.disabled = true;
  recordButton.classList.remove("recording");
  recordButtonLabel.textContent = "Record answer";
  setStatus("Processing");

  const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
  const form = new FormData();
  form.append("session_id", sessionId);
  form.append("audio", blob, "turn.webm");

  try {
    const response = await fetch("/turn/audio", {
      method: "POST",
      body: form,
    });

    if (!response.ok) throw new Error(await response.text());

    const data = await response.json();

    appendTurn("user", data.transcript);
    debugOutput.textContent = JSON.stringify(data.timings, null, 2);

    await playAssistant(data.audio_url, data.reply);
  } catch (error) {
    appendTurn("assistant", "Something went wrong. Please try again.");
    setStatus("Ready");
    recordButton.disabled = false;
    console.error(error);
  }
}
