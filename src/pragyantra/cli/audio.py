"""File/device audio commands; provider and device lifetimes are explicit."""

import asyncio
import json

from pragyantra.cli.records import text_record


async def listen(args):
    from pragyantra.providers.openai_services import openai_services

    if args.microphone:
        from pragyantra.inputs.microphone import record_microphone

        clip = await record_microphone(
            device=args.input_device,
            idle_timeout=args.listen_timeout.total_seconds(),
            sample_rate=args.sample_rate,
            threshold=args.energy_threshold,
            max_seconds=args.utterance_limit.total_seconds(),
            silence_seconds=args.silence_duration.total_seconds(),
        )
    else:
        from pragyantra.inputs.audio import load_audio

        clip = await asyncio.to_thread(load_audio, args.file)
    async with openai_services(
        transcription_model=args.transcription_model,
        timeout=args.timeout.total_seconds(),
    ) as provider:
        transcript = await provider.transcribe(clip)
    if args.json:
        print(
            json.dumps(
                {
                    **text_record(transcript),
                    "duration_seconds": clip.duration,
                }
            )
        )
    else:
        print(transcript.text)


async def speak(args):
    from pragyantra.outputs.audio import play_audio, save_audio
    from pragyantra.providers.openai_services import openai_services

    if args.output is not None and args.output.exists():
        raise ValueError("Output already exists; choose a new WAV path")
    async with openai_services(
        speech_model=args.speech_model,
        voice=args.voice_name,
        timeout=args.timeout.total_seconds(),
    ) as provider:
        clip = await provider.synthesize(args.text)
    if args.output:
        await asyncio.to_thread(save_audio, clip, args.output)
    if args.play:
        await play_audio(clip, device=args.output_device)
    print(
        json.dumps(
            {
                "source": clip.source,
                "duration_seconds": clip.duration,
                "output": str(args.output) if args.output else None,
                "speech_model": args.speech_model,
                "voice": args.voice_name,
            }
        )
    )


def devices():
    from pragyantra.inputs.microphone import _sounddevice

    sd = _sounddevice()
    try:
        listing = [
            dict(device, index=index) for index, device in enumerate(sd.query_devices())
        ]
        print(json.dumps(listing, ensure_ascii=False))
    except sd.PortAudioError as exc:
        raise ValueError("Could not enumerate audio devices") from exc
