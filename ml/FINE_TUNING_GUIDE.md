# HumanEye — Content Classifier Fine-Tuning Guide
# How to upgrade from the demo model to a production model trained on your own data.
# Time required: ~2 hours total. Cost: free (Google Colab T4).

=============================================================
 WHEN TO DO THIS
=============================================================

Do this AFTER your pilot customers are live and you have real data.
You need:
  - At least 500 human-written samples from your platform
    (real cover letters, reviews, etc. that users confirmed are genuine)
  - At least 500 AI-generated samples
    (run GPT-4/Claude on the same prompts your users get — these are your "fake" samples)

Do NOT do this before pilot. The demo model is good enough to show investors.
Fine-tuning on too-small data makes the model worse, not better.


=============================================================
 STEP 1: COLLECT TRAINING DATA
=============================================================

Format: a CSV with two columns — text, label

  text,label
  "I built this feature in March and it reduced load time by 40%...",human
  "I am excited to apply for this position. Furthermore, my extensive...",ai
  ...

Where to get human samples:
  - From pilot customer verifications where the user scored > 85 (very likely human)
  - Ask pilot customers to donate anonymized real submissions

Where to get AI samples:
  - Generate them yourself: take the same job descriptions your users apply to,
    run through GPT-4 with "write a cover letter for this job" — these are clean AI samples
  - Use the HuggingFace dataset: "Hello-SimpleAI/HC3" (Human ChatGPT Comparison Corpus)

Save as: ml_engine/training/data/classifier_training.csv


=============================================================
 STEP 2: FINE-TUNE ON GOOGLE COLAB (FREE T4 GPU)
=============================================================

Open: https://colab.research.google.com
Runtime → Change runtime type → T4 GPU

Paste and run this notebook:

─────────────────────────────────────────────────────────────
# Cell 1: Install
!pip install transformers datasets accelerate -q

# Cell 2: Load data
import pandas as pd
from datasets import Dataset
from sklearn.model_selection import train_test_split

df = pd.read_csv("classifier_training.csv")
df["label"] = df["label"].map({"human": 1, "ai": 0})

train_df, eval_df = train_test_split(df, test_size=0.2, random_state=42)
train_dataset = Dataset.from_pandas(train_df)
eval_dataset  = Dataset.from_pandas(eval_df)

# Cell 3: Tokenize
from transformers import AutoTokenizer

MODEL_BASE = "distilroberta-base"   # Smaller than roberta-large, faster to fine-tune
tokenizer = AutoTokenizer.from_pretrained(MODEL_BASE)

def tokenize(batch):
    return tokenizer(batch["text"], truncation=True, max_length=512, padding="max_length")

train_dataset = train_dataset.map(tokenize, batched=True)
eval_dataset  = eval_dataset.map(tokenize, batched=True)

# Cell 4: Train
from transformers import AutoModelForSequenceClassification, TrainingArguments, Trainer
import numpy as np
from sklearn.metrics import accuracy_score, f1_score

model = AutoModelForSequenceClassification.from_pretrained(
    MODEL_BASE,
    num_labels=2,
    id2label={0: "ai", 1: "human"},
    label2id={"ai": 0, "human": 1},
)

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, predictions),
        "f1": f1_score(labels, predictions, average="weighted"),
    }

training_args = TrainingArguments(
    output_dir="./humaneye-detector",
    num_train_epochs=3,
    per_device_train_batch_size=16,
    per_device_eval_batch_size=16,
    warmup_steps=100,
    weight_decay=0.01,
    evaluation_strategy="epoch",
    save_strategy="epoch",
    load_best_model_at_end=True,
    metric_for_best_model="f1",
    report_to="none",
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
    compute_metrics=compute_metrics,
)

trainer.train()

# Cell 5: Save
trainer.save_model("./humaneye-detector")
tokenizer.save_pretrained("./humaneye-detector")
print("Done. Download the humaneye-detector/ folder.")
─────────────────────────────────────────────────────────────

Expected output after 3 epochs (~90 minutes on T4):
  - accuracy: 0.91–0.95
  - f1: 0.90–0.94
  - False positive rate (AI labelled as human): < 5%


=============================================================
 STEP 3: DEPLOY YOUR FINE-TUNED MODEL
=============================================================

1. Download the humaneye-detector/ folder from Colab
   Files → right-click humaneye-detector → Download as zip

2. Extract and place at:
   ml_engine/saved_models/humaneye-detector/

3. Change one line in content_classifier.py:
   # Before:
   MODEL_NAME = "openai-community/roberta-large-openai-detector"

   # After:
   MODEL_NAME = "/app/ml_engine/saved_models/humaneye-detector"

4. Register the model with Security:
   python -m ml_engine.scripts.deploy_model \
     --model classifier \
     --file ml_engine/saved_models/humaneye-detector/pytorch_model.bin \
     --version 2.0.0 \
     --deployer "your-name"

5. Rebuild and restart the ML engine container:
   docker-compose build ml_engine && docker-compose up -d ml_engine

6. Verify it loaded:
   curl http://localhost:8001/health | python -m json.tool
   # Look for: "classifier": { "loaded": true, "hash_verified": true }


=============================================================
 WHAT CHANGES IN THE CODE
=============================================================

Nothing except MODEL_NAME. The classifier auto-detects the label scheme
of any model at startup (_detect_human_label). Your fine-tuned model
outputs "human"/"ai" labels which are handled automatically.

The statistical fallback always runs regardless of which model is loaded.
Your fine-tuned model replaces the transformer component only.


=============================================================
 DEMO vs PRODUCTION ACCURACY COMPARISON
=============================================================

  Model                               GPT-2 text  GPT-4 text  Fine-tuned domain
  ──────────────────────────────────────────────────────────────────────────────
  roberta-large-openai-detector       ~95%        ~60%        n/a
  chatgpt-detector-roberta            ~80%        ~85%        n/a
  Your fine-tuned humaneye-detector   ~85%        ~90%+       ~95%+

For investor demo: the openai detector is fine.
For paying customers: fine-tune after pilot data is available.
