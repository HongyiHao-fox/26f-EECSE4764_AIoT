
import os
import re
import csv
import json
import random
import argparse
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from google import genai

DATA_DIR = (
    Path(__file__).resolve().parent
    / "human+activity+recognition+using+smartphones"
    / "UCI HAR Dataset"
    / "UCI HAR Dataset"
)

RESULTS_DIR = (
    Path(__file__).resolve().parent / "results_gemini"
)

MODEL = "gemini-3.5-flash-lite"

LABELS = {
    0: "WALKING",
    1: "WALKING_UPSTAIRS",
    2: "WALKING_DOWNSTAIRS",
    3: "SITTING",
    4: "STANDING",
    5: "LAYING"
}

CHANNELS = [
    "total_acc_x",
    "total_acc_y",
    "total_acc_z",
    "body_gyro_x",
    "body_gyro_y",
    "body_gyro_z"
]


class UCIHARSignals(Dataset):

    def __init__(self, root, split="train"):

        if split not in ("train", "test"):
            raise ValueError("Invalid split")

        root = Path(root)
        base = root / split / "Inertial Signals"

        signals = []

        for channel in CHANNELS:

            filename = f"{channel}_{split}.txt"

            data = np.loadtxt(
                base / filename,
                dtype=np.float32
            )

            signals.append(data)


        self.x = torch.from_numpy(
            np.stack(signals, axis=1)
        )

        labels = np.loadtxt(
            root / split / f"y_{split}.txt",
            dtype=np.int64
        )


        self.y = torch.from_numpy(labels - 1)

        assert self.x.shape[1:] == (6, 128)
        assert len(self.x) == len(self.y)

    def __len__(self):
        return len(self.y)

    def __getitem__(self, index):

        x = self.x[index]
        y = int(self.y[index].item())

        return x, y, LABELS[y]


def load_data():

    train_set = UCIHARSignals(
        DATA_DIR, "train"
    )

    test_set = UCIHARSignals(
        DATA_DIR, "test"
    )

    train_loader = DataLoader(
        train_set,
        batch_size=32,
        shuffle=True
    )

    test_loader = DataLoader(
        test_set,
        batch_size=32,
        shuffle=False
    )

    print(
        f"Train: {len(train_set)} windows; "
        f"Test: {len(test_set)} windows"
    )

    for name, loader in [
        ("Train", train_loader),
        ("Test", test_loader)
    ]:

        xb, yb, _ = next(iter(loader))

        print(
            f"{name} batch: {tuple(xb.shape)}, "
            f"labels: {tuple(yb.shape)}"
        )

    return train_set, test_set






def format_sensor_data(x):

    if isinstance(x, torch.Tensor):
        x = x.detach().cpu().numpy()

    assert x.shape == (6, 128)

    lines = []

    for i, channel in enumerate(CHANNELS):

        values = ", ".join(
            f"{float(v):.4f}" for v in x[i]
        )

        lines.append(
            f"{channel}: [{values}]"
        )

    return "\n".join(lines)






def build_prompt(x, style="cot"):

    sensor_text = format_sensor_data(x)

    base = f"""
You are performing Human Activity Recognition
using smartphone IMU sensor data.

Device: Smartphone
Location: Waist
Dataset: UCI HAR

Sampling frequency: 50 Hz
Window length: 128 time steps
Duration: 2.56 seconds

Sensor channels:
- Total acceleration X/Y/Z (g)
- Body gyroscope X/Y/Z

Candidate activities:

WALKING
WALKING_UPSTAIRS
WALKING_DOWNSTAIRS
SITTING
STANDING
LAYING

Sensor data:

{sensor_text}

Question:
Which activity is being performed?

Choose exactly one candidate.
Do not invent measurements.
"""

    if style == "cot":

        instruction = """
Explain your reasoning step by step.

Discuss:
1. Dynamic or stationary motion.
2. Acceleration variation and periodicity.
3. Gyroscope patterns.
4. Which activity best matches the data.

Do not assume that small sensor fluctuations
necessarily mean the person is walking.

Finish with exactly one line:

ACTIVITY: LABEL

Replace LABEL with one of the six activities.
"""

    elif style == "direct":

        instruction = """
Give only the predicted activity.

Do not provide an explanation.

Output exactly one line:

ACTIVITY: LABEL

Replace LABEL with one of the six activities.
"""

    else:
        raise ValueError("Unknown prompt style")

    return base.strip() + "\n\n" + instruction.strip()






def create_client():

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing.\n"
            "Set it in PowerShell:\n"
            '$env:GEMINI_API_KEY="YOUR_KEY"'
        )

    return genai.Client(api_key=api_key)


def call_gemini(client, prompt):

    try:

        interaction = client.interactions.create(
            model=MODEL,
            input=prompt,
            generation_config={
                "thinking_level": "low"
            }
        )

        response_text = (
            interaction.output_text or ""
        ).strip()

        if not response_text:

            raise ValueError(
                "Gemini returned an empty response."
            )

        return {
            "text": response_text,
            "error": None
        }

    except Exception as e:

        error_message = (
            f"{type(e).__name__}: {str(e)}"
        )

        print("\n[GEMINI API ERROR]")
        print(error_message)

        return {
            "text": "",
            "error": error_message
        }






def parse_label(text):

    if not text:
        return "INVALID"

    text = text.upper()

    options = "|".join(
        sorted(
            LABELS.values(),
            key=len,
            reverse=True
        )
    )

    matches = re.findall(
        rf"ACTIVITY\s*:\s*({options})\b",
        text
    )

    if matches:
        return matches[-1]

    cleaned = text.strip(
        " \n\t.,:`*"
    )

    if cleaned in LABELS.values():
        return cleaned

    return "INVALID"






def save_results(records, summary=None):

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        RESULTS_DIR / "checkpoint1_results.json",
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            records,
            f,
            indent=2,
            ensure_ascii=False
        )

    fields = [
        "sample",
        "index",
        "true_label",
        "cot_prediction",
        "direct_prediction",
        "cot_correct",
        "direct_correct",
        "cot_error",
        "direct_error"
    ]

    with open(
        RESULTS_DIR / "checkpoint1_results.csv",
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields,
            extrasaction="ignore"
        )

        writer.writeheader()
        writer.writerows(records)

    if summary is not None:

        with open(
            RESULTS_DIR / "summary.json",
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                summary,
                f,
                indent=2,
                ensure_ascii=False
            )






def evaluate(test_set, client, n=10, seed=42):

    if n < 1 or n > len(test_set):
        raise ValueError("Invalid sample count")

    indices = random.Random(seed).sample(
        range(len(test_set)),
        n
    )

    records = []

    for i, index in enumerate(indices, start=1):

        x, y, true_label = test_set[index]

        print("\n" + "=" * 60)
        print(f"Sample {i}/{n}")
        print(f"Dataset index: {index}")
        print(f"Ground truth: {true_label}")
        print("=" * 60)

        cot_prompt = build_prompt(x, "cot")
        direct_prompt = build_prompt(x, "direct")


        if i == 1:

            RESULTS_DIR.mkdir(
                parents=True,
                exist_ok=True
            )

            (
                RESULTS_DIR / "cot_prompt.txt"
            ).write_text(
                cot_prompt,
                encoding="utf-8"
            )

            (
                RESULTS_DIR / "direct_prompt.txt"
            ).write_text(
                direct_prompt,
                encoding="utf-8"
            )


        print("\nCalling Gemini - CoT...")

        cot_result = call_gemini(
            client,
            cot_prompt
        )


        print("\nCalling Gemini - Direct...")

        direct_result = call_gemini(
            client,
            direct_prompt
        )

        cot_prediction = parse_label(
            cot_result["text"]
        )

        direct_prediction = parse_label(
            direct_result["text"]
        )

        cot_correct = (
            cot_prediction == true_label
        )

        direct_correct = (
            direct_prediction == true_label
        )

        print("\n--- CoT Response ---")
        print(
            cot_result["text"] or "[EMPTY]"
        )

        print("\n--- Direct Response ---")
        print(
            direct_result["text"] or "[EMPTY]"
        )

        print("\n--- Classification ---")
        print(f"True:   {true_label}")
        print(f"CoT:    {cot_prediction}")
        print(f"Direct: {direct_prediction}")

        record = {
            "sample": i,
            "index": index,
            "true_label": true_label,
            "cot_prediction": cot_prediction,
            "direct_prediction": direct_prediction,
            "cot_correct": cot_correct,
            "direct_correct": direct_correct,
            "cot_response": cot_result["text"],
            "direct_response": direct_result["text"],
            "cot_error": cot_result["error"],
            "direct_error": direct_result["error"]
        }

        records.append(record)

        save_results(records)


    cot_correct_count = sum(
        r["cot_correct"] for r in records
    )

    direct_correct_count = sum(
        r["direct_correct"] for r in records
    )

    agreement = sum(
        r["cot_prediction"] == r["direct_prediction"]
        and r["cot_prediction"] != "INVALID"
        for r in records
    )

    cot_invalid = sum(
        r["cot_prediction"] == "INVALID"
        for r in records
    )

    direct_invalid = sum(
        r["direct_prediction"] == "INVALID"
        for r in records
    )

    cot_accuracy = cot_correct_count / n
    direct_accuracy = direct_correct_count / n
    agreement_rate = agreement / n

    summary = {
        "model": MODEL,
        "num_samples": n,
        "seed": seed,
        "cot_accuracy": cot_accuracy,
        "direct_accuracy": direct_accuracy,
        "prompt_agreement": agreement_rate,
        "cot_invalid": cot_invalid,
        "direct_invalid": direct_invalid
    }

    save_results(records, summary)

    print("\n" + "=" * 60)
    print("CHECKPOINT 1 SUMMARY")
    print("=" * 60)

    print(f"Model: {MODEL}")

    print(
        f"CoT Accuracy: "
        f"{cot_correct_count}/{n} = "
        f"{cot_accuracy * 100:.1f}%"
    )

    print(
        f"Direct Accuracy: "
        f"{direct_correct_count}/{n} = "
        f"{direct_accuracy * 100:.1f}%"
    )

    print(
        f"Prompt Agreement: "
        f"{agreement_rate * 100:.1f}%"
    )

    print(
        f"Invalid Outputs: "
        f"CoT={cot_invalid}, "
        f"Direct={direct_invalid}"
    )

    if cot_invalid or direct_invalid:
        print(
            "\nWARNING: Some outputs are invalid."
        )
        print(
            "Do not report invalid API calls "
            "as normal classification results."
        )

    print("\nResults saved to:")
    print(RESULTS_DIR)






def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--num-samples",
        type=int,
        default=10
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42
    )

    args = parser.parse_args()

    print("=" * 60)
    print("EECS E4764 - Lab 6")
    print("Checkpoint 1 - Gemini HAR")
    print("=" * 60)

    print("\nDataset:")
    print(DATA_DIR)

    if not DATA_DIR.is_dir():
        raise FileNotFoundError(DATA_DIR)

    train_set, test_set = load_data()

    print("\nInitializing Gemini client...")

    client = create_client()

    print(f"Model: {MODEL}")

    try:
        evaluate(
            test_set,
            client,
            n=args.num_samples,
            seed=args.seed
        )
    finally:
        client.close()


if __name__ == "__main__":
    main()
