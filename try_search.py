from retrieval.policy import PolicyIndex, retrieve

index = PolicyIndex()
print(len(index.chunks), "chunks loaded\n")

for q in ["customer has an open complaint",
          "what if the customer wants us to stop contacting them",
          "how is seasonal decline treated",
          "best pizza recipe in town"]:
    r = retrieve(index, q)
    print(q, "->", r["status"], [h["ref"] for h in r["hits"]],
          "| tries:", len(r["attempts"]))