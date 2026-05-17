import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router';
import { Button } from '../../components/ui/button';
import { Sparkles, Mic, Square, Play, AlertCircle, Check } from 'lucide-react';
import { uploadVoiceReference, upsertUser } from '../../lib/api';

export default function VoiceRecording() {
  const [isRecording, setIsRecording] = useState(false);
  const [hasRecorded, setHasRecorded] = useState(false);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [recordingTime, setRecordingTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSavingReference, setIsSavingReference] = useState(false);
  const [playbackUrl, setPlaybackUrl] = useState<string | null>(null);
  const [playbackInfo, setPlaybackInfo] = useState<{ mimeType: string; size: number; durationSec?: number } | null>(null);
  const [inputLevel, setInputLevel] = useState(0);
  const [silenceWarning, setSilenceWarning] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);
  const playbackAudioElRef = useRef<HTMLAudioElement | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number | null>(null);
  const navigate = useNavigate();

  const userName = localStorage.getItem('userName') || 'there';

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
        audioUrlRef.current = null;
      }
      if (rafRef.current != null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
      if (audioCtxRef.current) {
        audioCtxRef.current.close().catch(() => undefined);
        audioCtxRef.current = null;
      }
    };
  }, []);

  const stopLevelMeter = () => {
    if (rafRef.current != null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    analyserRef.current = null;
    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => undefined);
      audioCtxRef.current = null;
    }
    setInputLevel(0);
  };

  const startLevelMeter = (stream: MediaStream) => {
    stopLevelMeter();
    try {
      const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!Ctx) return;
      const ctx = new Ctx();
      audioCtxRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 2048;
      source.connect(analyser);
      analyserRef.current = analyser;

      const data = new Uint8Array(analyser.fftSize);
      const tick = () => {
        const a = analyserRef.current;
        if (!a) return;
        a.getByteTimeDomainData(data);
        // Compute normalized RMS from 8-bit PCM centered at 128
        let sumSq = 0;
        for (let i = 0; i < data.length; i++) {
          const v = (data[i] - 128) / 128;
          sumSq += v * v;
        }
        const rms = Math.sqrt(sumSq / data.length);
        setInputLevel(rms);
        rafRef.current = requestAnimationFrame(tick);
      };
      rafRef.current = requestAnimationFrame(tick);
    } catch {
      // Ignore meter failures; recording can still work.
    }
  };

  useEffect(() => {
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }

    if (!audioBlob) {
      setPlaybackUrl(null);
      setPlaybackInfo(null);
      return;
    }

    const url = URL.createObjectURL(audioBlob);
    audioUrlRef.current = url;
    setPlaybackUrl(url);
    setPlaybackInfo({ mimeType: audioBlob.type || '(unknown)', size: audioBlob.size });
    setSilenceWarning(null);

    return () => {
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
        audioUrlRef.current = null;
      }
    };
  }, [audioBlob]);

  const startRecording = async () => {
    try {
      setError(null);
      setSilenceWarning(null);
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      startLevelMeter(stream);
      // Choose a browser-supported mimeType for best playback compatibility (Safari vs Chrome differs).
      const preferredMimeTypes = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/mp4',
      ];
      const chosenMimeType =
        preferredMimeTypes.find((t) => (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported?.(t))) ??
        undefined;

      const mediaRecorder = chosenMimeType
        ? new MediaRecorder(stream, { mimeType: chosenMimeType })
        : new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        stopLevelMeter();
        const blobType =
          mediaRecorder.mimeType ||
          audioChunksRef.current[0]?.type ||
          chosenMimeType ||
          'audio/webm';

        const nextBlob = new Blob(audioChunksRef.current, { type: blobType });
        if (nextBlob.size === 0) {
          setAudioBlob(null);
          setHasRecorded(false);
          setError('Recording was empty. Please try again and make sure your microphone is working.');
          stream.getTracks().forEach(track => track.stop());
          return;
        }
        setAudioBlob(nextBlob);
        setHasRecorded(true);
        stream.getTracks().forEach(track => track.stop());
      };

      // Timeslice helps ensure we actually receive data chunks on some browsers/devices.
      mediaRecorder.start(250);
      setIsRecording(true);
      setRecordingTime(0);

      // Start timer
      timerRef.current = setInterval(() => {
        setRecordingTime(prev => {
          if (prev >= 10) {
            stopRecording();
            return 10;
          }
          return prev + 1;
        });
      }, 1000);
    } catch (error) {
      stopLevelMeter();
      console.error('Error accessing microphone:', error);
      if (error instanceof Error) {
        if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
          setError('Microphone access was denied. Please allow microphone access in your browser settings, or skip this step.');
        } else if (error.name === 'NotFoundError') {
          setError('No microphone found. Please connect a microphone or skip this step.');
        } else {
          setError('Unable to access microphone. Please check your device settings or skip this step.');
        }
      }
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
  };

  const playRecording = async () => {
    if (!audioBlob || isPlaying) return;
    setError(null);
    const el = playbackAudioElRef.current;
    if (!el) {
      setError('Playback element not ready. Please try again.');
      return;
    }

    try {
      el.currentTime = 0;
      await el.play();
      // isPlaying is driven by audio events below
    } catch {
      setError('Playback was blocked or failed. Try clicking Play again, or re-recording.');
    }
  };

  const handleContinue = async () => {
    if (!hasRecorded || !audioBlob) return;

    const targetName = localStorage.getItem('userName') || 'User';
    setIsSavingReference(true);
    try {
      // Ensure we have a user row so uploads can be associated to the correct user_id.
      let userId = localStorage.getItem('userId') || '';
      if (!userId) {
        try {
          const email = localStorage.getItem('userEmail') || '';
          const name = localStorage.getItem('userName') || '';
          const occupation = localStorage.getItem('userOccupation') || '';
          const seniorityLevel = localStorage.getItem('userSeniorityLevel') || '';
          const rankedSkillsRaw = localStorage.getItem('rankedSkills');
          const otherFocus = localStorage.getItem('otherFocus') || '';
          const rankedSkills =
            rankedSkillsRaw && rankedSkillsRaw.trim()
              ? (JSON.parse(rankedSkillsRaw) as string[])
              : undefined;
          const u = await upsertUser({
            email,
            name,
            occupation,
            seniorityLevel,
            rankedSkills,
            otherFocus,
            voiceRecorded: true,
          });
          userId = u.id;
          localStorage.setItem('userId', u.id);
        } catch {
          // ignore; we'll still upload the voice reference without user association.
        }
      }

      await uploadVoiceReference({
        targetName,
        blob: audioBlob,
        filename: `${targetName}-voice-reference.webm`,
        email: localStorage.getItem('userEmail') || undefined,
        userId: userId || undefined,
      });
      localStorage.setItem('voiceRecorded', 'true');
      navigate('/dashboard');
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to save voice reference.';
      setError(`Could not save your voice sample. You can retry, or skip for now. Details: ${msg}`);
    } finally {
      setIsSavingReference(false);
    }
  };

  // Skipping voice recording is intentionally not allowed.

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-purple-50">
      <div className="p-8">
        <div className="flex items-center gap-2">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center">
            <Sparkles className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-2xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
            Guidepost
          </h1>
        </div>
      </div>

      <div className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          {/* Progress indicator */}
          <div className="flex items-center justify-center gap-2 mb-8">
            <div className="w-8 h-1 rounded-full bg-gradient-to-r from-indigo-600 to-purple-600" />
            <div className="w-8 h-1 rounded-full bg-gradient-to-r from-indigo-600 to-purple-600" />
            <div className="w-8 h-1 rounded-full bg-gradient-to-r from-indigo-600 to-purple-600" />
            <div className="w-8 h-1 rounded-full bg-gradient-to-r from-indigo-600 to-purple-600" />
            <div className="w-8 h-1 rounded-full bg-gradient-to-r from-indigo-600 to-purple-600" />
          </div>

          <div className="bg-white rounded-3xl shadow-2xl shadow-indigo-100 p-10">
            <div className="text-center mb-8">
              <h2 className="text-4xl font-bold mb-3 text-slate-900">Voice setup</h2>
              <p className="text-slate-600">
                Record a 10-second voice sample so we can recognize you in conversations
              </p>
            </div>

            <div className="space-y-6">
              <div className="p-6 bg-gradient-to-br from-indigo-50 to-purple-50 rounded-2xl border border-indigo-100">
                <p className="text-center italic text-slate-700 leading-relaxed">
                  &quot;Hi, my name is{' '}
                  <span className="font-semibold text-indigo-600">{userName}</span>. I&apos;m recording this sample so the
                  system can recognize my voice in conversations.&quot;
                </p>
              </div>

              {error && (
              <div className="p-4 bg-red-50 border-2 border-red-200 rounded-xl flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm text-red-800">{error}</p>
                </div>
              </div>
            )}

            {silenceWarning && (
              <div className="p-4 bg-yellow-50 border-2 border-yellow-200 rounded-xl flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-yellow-700 shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm text-yellow-800">{silenceWarning}</p>
                </div>
              </div>
            )}

            <div className="flex flex-col items-center gap-6 py-6">
              {!isRecording && !hasRecorded && (
                <Button
                  onClick={startRecording}
                  size="lg"
                  className="w-24 h-24 rounded-full bg-gradient-to-br from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 shadow-xl shadow-indigo-300 hover:shadow-2xl hover:shadow-indigo-400 transition-all duration-300 hover:scale-105"
                >
                  <Mic className="w-8 h-8" />
                </Button>
              )}

              {isRecording && (
                <div className="flex flex-col items-center gap-4">
                  <Button
                    onClick={stopRecording}
                    size="lg"
                    variant="destructive"
                    className="w-24 h-24 rounded-full shadow-xl shadow-red-300 hover:shadow-2xl hover:shadow-red-400 transition-all duration-300 hover:scale-105"
                  >
                    <Square className="w-8 h-8" />
                  </Button>
                  <div className="text-center">
                    <div className="text-5xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent mb-2">
                      {recordingTime}s
                    </div>
                    <div className="flex items-center gap-2 text-slate-600 justify-center">
                      <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                      Recording...
                    </div>
                  </div>

                  <div className="w-full">
                    <div className="h-2.5 w-full rounded-full bg-slate-200 overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-green-500 to-emerald-600 transition-[width] duration-75"
                        style={{ width: `${Math.min(100, Math.max(2, inputLevel * 250))}%` }}
                      />
                    </div>
                    <div className="mt-2 text-center text-xs text-slate-500">
                      {inputLevel < 0.01 ? 'Mic level: very low' : 'Mic level: OK'}
                    </div>
                  </div>
                </div>
              )}

              {hasRecorded && (
                <div className="flex flex-col items-center gap-4 w-full">
                  <div className="flex items-center gap-3 px-6 py-3 bg-gradient-to-r from-green-50 to-emerald-50 border-2 border-green-200 rounded-full">
                    <div className="w-8 h-8 rounded-full bg-green-500 flex items-center justify-center">
                      <Check className="w-5 h-5 text-white" />
                    </div>
                    <span className="font-semibold text-green-700">Recording complete!</span>
                  </div>

                  {playbackInfo && (
                    <div className="w-full text-xs text-gray-500">
                      <div>Format: {playbackInfo.mimeType}</div>
                      <div>Size: {Math.round(playbackInfo.size / 1024)} KB{typeof playbackInfo.durationSec === 'number' ? ` • Duration: ${playbackInfo.durationSec.toFixed(1)}s` : ''}</div>
                    </div>
                  )}

                  <audio
                    ref={playbackAudioElRef}
                    className="w-full"
                    controls
                    playsInline
                    src={playbackUrl ?? undefined}
                    onPlay={() => setIsPlaying(true)}
                    onPause={() => setIsPlaying(false)}
                    onEnded={() => setIsPlaying(false)}
                    onLoadedMetadata={(e) => {
                      const d = e.currentTarget.duration;
                      if (Number.isFinite(d)) {
                        setPlaybackInfo((prev) => (prev ? { ...prev, durationSec: d } : prev));
                      }
                    }}
                    onCanPlay={() => {
                      const el = playbackAudioElRef.current;
                      if (!el) return;
                      // Ensure we aren't accidentally muted/quiet.
                      el.muted = false;
                      if (el.volume < 0.5) el.volume = 1;
                    }}
                    onTimeUpdate={() => {
                      // If time is advancing but we never saw meaningful mic input during recording,
                      // the recording likely contains silence (wrong input device, OS mic muted, etc).
                      if (recordingTime > 0 && inputLevel < 0.01 && !silenceWarning) {
                        // Don't spam; set once.
                        setSilenceWarning(
                          "This recording is playing, but it looks like your microphone input was extremely low while recording. Check macOS mic input level and the selected Chrome input device, then re-record."
                        );
                      }
                    }}
                    onError={() => {
                      setIsPlaying(false);
                      setError('Could not play back this recording in your browser. Try re-recording, or use a different browser.');
                    }}
                  />

                  <div className="flex gap-3 w-full">
                    <Button
                      onClick={playRecording}
                      variant="outline"
                      disabled={isPlaying}
                      className="flex-1 h-12 rounded-xl border-slate-200 hover:border-indigo-200 hover:bg-indigo-50"
                    >
                      <Play className="w-4 h-4 mr-2" />
                      {isPlaying ? 'Playing...' : 'Play'}
                    </Button>
                    <Button
                      onClick={() => {
                        setHasRecorded(false);
                        setAudioBlob(null);
                        setRecordingTime(0);
                        setError(null);
                      }}
                      variant="outline"
                      className="flex-1 h-12 rounded-xl border-slate-200 hover:border-indigo-200 hover:bg-indigo-50"
                    >
                      Re-record
                    </Button>
                  </div>
                </div>
              )}
            </div>

            {hasRecorded && (
              <Button
                onClick={handleContinue}
                className="w-full h-12 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 shadow-lg shadow-indigo-200"
                disabled={isSavingReference}
              >
                {isSavingReference ? 'Saving voice sample…' : 'Continue to Chat'}
              </Button>
            )}

            {!hasRecorded && (
              <div className="space-y-3">
                {!isRecording && (
                  <p className="text-center text-sm text-gray-500">
                    Click the microphone to start recording. This step is required to continue.
                  </p>
                )}
              </div>
            )}
          </div>
          </div>
        </div>
      </div>
    </div>
  );
}