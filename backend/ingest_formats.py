# ingest_formats.py — run this ONCE to feed all enquiry texts into ChromaDB
# This is not part of the web server, just a standalone script

import json
from embeddings import model, format_collection

# Step 1: Define all enquiries with code, topic and text
# This is structured from the Freehold Title Check Enquiries document
# Add all enquiries here — we'll start with a sample and you can expand

enquiries = [
    # ── PART 1 — Contract ──────────────────────────────────────
    {
        "code": "A1",
        "section": "Contract",
        "topic": "Title number mismatch between title documents and contract",
        "trigger": "title numbers on official copies and contract are different",
        "text": "We note that the Title Number referred to in the documents of title supplied and the Title Number on the Contract document are different. Please clarify."
    },
    {
        "code": "A3",
        "section": "Contract",
        "topic": "Deposit not held as stakeholder",
        "trigger": "contract does not state deposit held as stakeholder",
        "text": "We note that the contract does not provide that the deposit is held by you as Stakeholder. This is not acceptable and we require special condition XX to be deleted from the contract."
    },
    {
        "code": "A4",
        "section": "Contract",
        "topic": "Limited title guarantee instead of full title guarantee",
        "trigger": "contract states limited title guarantee",
        "text": "We note that the contract states that the property will be sold with Limited Title Guarantee. We must insist that the property is sold with Full Title Guarantee and we have amended the contract accordingly."
    },
    # ── PART 4 — Official Copies ───────────────────────────────
    {
        "code": "D1",
        "section": "Official Copies",
        "topic": "Official copy entries not provided",
        "trigger": "no official copies supplied",
        "text": "Please provide up to date Official Copy Entries and Title Plan."
    },
    {
        "code": "D2",
        "section": "Official Copies",
        "topic": "Official copies out of date",
        "trigger": "official copies more than 6 or 12 months old",
        "text": "We note that the Official Copy Entries supplied are more than 12 months old. Please provide up to date Official Copy Entries."
    },
    {
        "code": "D4",
        "section": "Official Copies",
        "topic": "Missing deed or document referred to in title register",
        "trigger": "title register refers to deed or document not supplied",
        "text": "We note that the Title Registers refer to a Transfer/Conveyance/Deed/Plan dated (insert date) at entry X of the Property/Charges Register. Please provide a copy of the same."
    },
    # ── PART 5 — Property Information Form ────────────────────
    {
        "code": "E6",
        "section": "Property Information Form",
        "topic": "Parking permit details not provided",
        "trigger": "seller indicates parking permit required but no details given",
        "text": "The seller has indicated that a parking permit is required to park at/outside the property but not provided details of the same. Please provide further details as to how to obtain a permit and the costs of the same."
    },
    {
        "code": "E7",
        "section": "Property Information Form",
        "topic": "EPC not supplied",
        "trigger": "no EPC provided and none available online",
        "text": "The seller has not supplied an EPC and no EPC is available via the online register. Please have the seller obtain and supply a valid EPC for the property."
    },
    {
        "code": "E9",
        "section": "Property Information Form",
        "topic": "Occupier consent required",
        "trigger": "occupiers at property who need to sign consent",
        "text": "We note from the Property Information Form that (name of occupier) is/are currently an occupier at the Property. Please confirm that they are agreeable to the sale of the Property and will sign the contract to confirm vacant possession will be given on completion, and that you will not allow exchange to take place until you are in possession of the necessary signed consent."
    },
    # ── PART 6 — Alterations ──────────────────────────────────
    {
        "code": "F3",
        "section": "Alterations",
        "topic": "FENSA certificate for replacement windows",
        "trigger": "windows or doors replaced, no FENSA certificate provided",
        "text": "Please provide a copy of the FENSA Certificate in respect of the replacement windows/doors installed at the property in (year)."
    },
    {
        "code": "F3b",
        "section": "Alterations",
        "topic": "Gas Safe certificate for new boiler or central heating",
        "trigger": "new boiler or central heating installed, no Gas Safe certificate",
        "text": "Please provide a copy of the Gas Safe/CORGI certificate in respect of the new boiler/central heating system installed at the property in (year)."
    },
    {
        "code": "F3c",
        "section": "Alterations",
        "topic": "Electrical works certificate",
        "trigger": "electrical works carried out, no competent persons certificate",
        "text": "Please provide a copy of the relevant Building Regulations or Competent Persons Scheme certificate in respect of electrical works carried out at the property in (year)."
    },
    # ── PART 9 — Rights of Way ────────────────────────────────
    {
        "code": "J1",
        "section": "Rights of Way",
        "topic": "Unadopted road access enquiry",
        "trigger": "access road not adopted by local authority",
        "text": "We note that the access road is not a public highway and is not adopted by the Local Authority. Please confirm whether the Seller has ever encountered any problems exercising the right of way to gain access to the property and whether any contributions have been requested or made in respect of the maintenance and repair of access."
    },
    # ── PART 10 — Additional ──────────────────────────────────
    {
        "code": "K4",
        "section": "Additional",
        "topic": "Solar panels enquiry",
        "trigger": "solar panels present at property",
        "text": "We note that there are Solar Panels at the property. We enclose our additional Solar Panel enquiries which please complete and return."
    },
]

def ingest_all_enquiries():
    """
    Converts all enquiry texts to vectors and stores in ChromaDB format_library collection
    Run this script once — or whenever you add new enquiry formats
    """

    print(f"Ingesting {len(enquiries)} enquiries into format library...")

    # Step 2: Build text to embed — combine all fields for richer search
    # We embed a combination of topic + trigger + text
    # so the AI can find the right enquiry by any of these
    texts_to_embed = []
    for e in enquiries:
        combined = f"Code: {e['code']}. Section: {e['section']}. Topic: {e['topic']}. When to use: {e['trigger']}. Enquiry text: {e['text']}"
        texts_to_embed.append(combined)

    # Step 3: Generate embeddings
    print("Generating embeddings...")
    embeddings = model.encode(texts_to_embed).tolist()

    # Step 4: Store in ChromaDB
    ids = [f"enquiry_{e['code']}" for e in enquiries]
    metadatas = [
        {
            "code": e["code"],
            "section": e["section"],
            "topic": e["topic"],
            "trigger": e["trigger"]
        }
        for e in enquiries
    ]
    documents = [e["text"] for e in enquiries]   # store just the text for retrieval

    format_collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas
    )

    print(f"Done! {len(enquiries)} enquiries stored in format_library collection.")
    print("Enquiry codes stored:", [e["code"] for e in enquiries])

if __name__ == "__main__":
    ingest_all_enquiries()