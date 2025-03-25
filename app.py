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
    merge: bool = False

    @property
    def length(self):
        return len(self.canonical)

    @property
    def end(self):
        return len(self.canonical) + self.start


@dataclass
class Doc:
    id: int
    title: str
    text: str
    lines: List[Line] = field(default_factory=list)

    def preprocess_lines(self):
        """Ensure that any uncovered text is assigned an empty Line object."""
        new_lines = []
        last_end = 0
        line_id = 1  # Start IDs at 1

        # Sort lines by start index
        sorted_lines = sorted(self.lines, key=lambda l: l.start)

        for line in sorted_lines:
            # If there's a gap before this line, create an empty line
            if line.start > last_end:
                if self.text[last_end:line.start].strip():
                    new_lines.append(
                        Line(id=line_id, start=last_end, canonical=self.text[last_end:line.start], normalized="")
                    )
                    line_id += 1

            # Add the actual mapped line
            new_lines.append(Line(id=line_id, start=line.start, canonical=line.canonical, normalized=line.normalized))
            line_id += 1
            last_end = line.end  # Move last_end forward

        # If there's text left at the end, add an empty line
        if last_end < len(self.text) and self.text[last_end:].strip():
            new_lines.append(Line(id=line_id, start=last_end, canonical=self.text[last_end:], normalized=""))

        self.lines = new_lines  # Replace with preprocessed lines


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
        elements[j["uid"]].preprocess_lines()

@app.route("/")
def index():
    # Pass the documents to the template
    return render_template("index.html", documents=elements)


@app.route("/document/<doc_id>/lines") # Should deal with lines / page
def lines(doc_id):
    doc_id = int(doc_id)
    return render_template("lines.html", lines=elements[doc_id].lines, document=elements[doc_id])

app.run(debug=True)