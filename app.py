from flask import Flask, render_template
import json
from typing import List
from dataclasses import dataclass, field


@dataclass
class Line:
    id: int
    start: int
    canonical: str
    normalized: str
    status: str = "Pending"

    @property
    def length(self):
        return len(self.canonical)


@dataclass
class Doc:
    id: int
    title: str
    text: str
    lines: List[Line] = field(default_factory=list)


app = Flask(__name__)

with open("source/n10.jsonl") as f:
    elements = {}
    for line in f:
        j = json.loads(line)
        elements[j["uid"]] = Doc(
            j["uid"],
            j["id"],
            j["text"],
            lines=[
                Line(
                    idx,
                    line["begin"],
                    canonical=line["text"],
                    normalized=line["wits"][0]["text"]
                )
                for idx, line in enumerate(j["lines"])
                if line.get("wits")
            ]
        )

@app.route("/")
def index():
    # Pass the documents to the template
    return render_template("index.html", documents=elements)


@app.route("/document/<int:doc_id>/lines") # Should deal with lines / page
def lines(doc_id):
    return render_template("lines.html", lines=elements[doc_id].lines, document=elements[doc_id])

app.run()