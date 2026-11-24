"""FAQ, care values, anatomy guide, visit steps and gallery content."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.content.clinic import CLINIC


# --------------------------------------------------------------------------- FAQ
@dataclass(frozen=True)
class FAQ:
    question: str
    answer: tuple[str, ...]
    verified: bool = True  # False -> shows a review marker; excluded from FAQPage JSON-LD


FAQS: tuple[FAQ, ...] = (
    FAQ(
        "How can I request an appointment?",
        (
            "You can request an appointment using the online appointment form or by calling the "
            f"clinic on {CLINIC.phone_display}.",
            "An online request is not a confirmed booking. The clinic team will contact you to confirm availability.",
        ),
    ),
    FAQ(
        "Where is the clinic located?",
        (
            f"{CLINIC.name} is in {CLINIC.locality}, {CLINIC.area}, {CLINIC.city}. "
            f"Please call {CLINIC.phone_display} for directions.",
        ),
    ),
    FAQ(
        "What are the consultation hours?",
        (
            f"Morning consultations are from {CLINIC.sessions[0].display} and evening "
            f"consultations are from {CLINIC.sessions[1].display}.",
            "Please call the clinic to check availability on a particular day.",
        ),
    ),
    FAQ(
        "Is my appointment confirmed when I submit the online form?",
        (
            "No. Submitting the form sends a request to the clinic. Your appointment is confirmed "
            "only when the clinic team contacts you.",
        ),
    ),
    FAQ(
        "How can I contact the clinic?",
        (
            f"Call {CLINIC.phone_display} during consultation hours, or send a message using the "
            "contact form on this website.",
        ),
    ),
    FAQ(
        "Can I use this website in an emergency?",
        (
            "No. This website and its forms are not monitored for emergencies. For a serious "
            "injury or medical emergency, call 112 or 108, or go to the nearest hospital "
            "emergency department.",
        ),
    ),
    FAQ(
        "What should I bring to my appointment?",
        (
            "It can help to bring any previous medical reports, X-rays or scans, prescriptions and "
            "a list of the medicines you currently take.",
        ),
        verified=False,  # TODO(clinic): confirm this guidance
    ),
)


# --------------------------------------------------------------------------- Care values
@dataclass(frozen=True)
class Value:
    icon: str
    title: str
    text: str


VALUES: tuple[Value, ...] = (
    Value(
        "listen",
        "Individual Attention",
        "Your concerns are heard and considered in the context of your daily life and activities.",
    ),
    Value(
        "speech",
        "Clear Communication",
        "Explanations in simple, everyday language so you understand your condition and options.",
    ),
    Value(
        "movement",
        "Focus on Movement",
        "Care that keeps your comfort and everyday movement at the centre of every conversation.",
    ),
    Value(
        "support",
        "Supportive Experience",
        "A calm, respectful and welcoming setting for patients of every age.",
    ),
)


# --------------------------------------------------------------------------- Visit steps
VISIT_STEPS: tuple[tuple[str, str], ...] = (
    ("Send a request", "Use the online form or call the clinic with your preferred date and session."),
    ("We call to confirm", "The clinic team contacts you to confirm a suitable consultation time."),
    ("Your consultation", "Discuss your symptoms and have the affected area examined."),
    ("Your next steps", "Understand the findings and the options that may help you move better."),
)


# --------------------------------------------------------------------------- Anatomy guide
@dataclass(frozen=True)
class AnatomyRegion:
    key: str
    label: str
    title: str
    text: str
    everyday: tuple[str, ...]
    service_slug: str


ANATOMY: tuple[AnatomyRegion, ...] = (
    AnatomyRegion(
        "shoulder",
        "Shoulder",
        "Shoulder",
        "Shoulder discomfort can make reaching overhead, lifting or sleeping on one side "
        "uncomfortable. An examination can help understand what may be contributing.",
        ("Reaching for a shelf", "Combing hair", "Carrying bags"),
        "joint-pain-evaluation",
    ),
    AnatomyRegion(
        "spine",
        "Spine",
        "Back and Spine",
        "Back or neck pain can affect sitting, standing and everyday work. A clinical evaluation "
        "can help identify possible causes and appropriate next steps.",
        ("Sitting at a desk", "Bending to lift", "Turning your head"),
        "back-and-spine-concerns",
    ),
    AnatomyRegion(
        "hip",
        "Hip",
        "Hip",
        "Hip pain may be felt in the groin, thigh or buttock and can make walking or getting up "
        "from a chair harder. An assessment can help find the likely source.",
        ("Getting out of a chair", "Putting on shoes", "Walking longer distances"),
        "knee-and-hip-concerns",
    ),
    AnatomyRegion(
        "knee",
        "Knee",
        "Knee",
        "Knee pain can affect everyday activities such as walking and climbing stairs. A clinical "
        "evaluation can help identify possible causes.",
        ("Climbing stairs", "Squatting or sitting cross-legged", "Walking on uneven ground"),
        "knee-and-hip-concerns",
    ),
    AnatomyRegion(
        "ankle",
        "Ankle",
        "Ankle and Foot",
        "Ankle sprains or ongoing ankle pain can affect balance and walking. Assessment can help "
        "guide a safe recovery.",
        ("Walking on uneven ground", "Standing for long periods", "Running or playing sport"),
        "sports-and-movement-injuries",
    ),
)


# --------------------------------------------------------------------------- Gallery
@dataclass(frozen=True)
class GalleryItem:
    key: str
    title: str
    caption: str
    image: str | None = None  # base path under static/images without size/extension
    width: int = 0
    height: int = 0
    alt: str = ""
    layout: str = "standard"  # standard | tall | wide | wide-md (wide from tablet up)
    sizes: tuple[int, ...] = field(default_factory=tuple)


_PENDING = " — to be supplied by the clinic."

GALLERY: tuple[GalleryItem, ...] = (
    GalleryItem(
        "doctor",
        "Dr. Arun Selvan R",
        "Professional portrait of Dr. Arun Selvan R, Consultant Orthopaedic Surgeon.",
        image="doctor/portrait",
        width=1122,
        height=1402,
        alt="Dr. Arun Selvan R in a white coat with arms folded",
        layout="tall",
        sizes=(480, 800, 1122),
    ),
    # TODO(clinic): replace placeholders with approved, real photographs of the clinic.
    GalleryItem("exterior", "Clinic exterior", f"Photograph of the clinic entrance{_PENDING}", layout="wide"),
    GalleryItem("reception", "Reception", f"Photograph of the reception area{_PENDING}"),
    GalleryItem("consultation", "Consultation room", f"Photograph of the consultation room{_PENDING}"),
    GalleryItem("waiting", "Waiting area", f"Photograph of the waiting area{_PENDING}"),
    GalleryItem("signage", "Clinic signage", f"Photograph of the clinic signage{_PENDING}", layout="wide-md"),
)
