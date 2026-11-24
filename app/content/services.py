"""Proposed orthopaedic service categories.

IMPORTANT: these are proposed content categories for layout, NOT confirmed
clinic services. Every entry has `approved=False` and shows an "awaiting
clinic review" marker until the clinic reviews the wording and sets
`approved=True`. Do not add treatments, outcomes or claims the clinic has not
confirmed.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Service:
    slug: str
    title: str
    short: str
    icon: str
    summary: str
    overview: tuple[str, ...]
    signs: tuple[str, ...]
    consultation: tuple[str, ...]
    anatomy: tuple[str, ...] = field(default_factory=tuple)
    featured: bool = False
    approved: bool = False  # TODO(clinic): review wording, then set True

    @property
    def path(self) -> str:
        return f"/services/{self.slug}"


_CONSULT_COMMON = (
    "A conversation about your symptoms, daily activities and any previous injuries or treatment.",
    "A physical examination of the affected area and how it moves.",
    "If needed, the doctor may advise tests such as X-rays or scans to understand the problem better.",
    "A clear explanation of the findings and a discussion of suitable next steps.",
)

SERVICES: tuple[Service, ...] = (
    Service(
        slug="general-orthopaedic-consultation",
        title="General Orthopaedic Consultation",
        short="A careful first assessment for bone, joint, muscle and movement concerns.",
        icon="stethoscope",
        summary=(
            "Not sure where your pain is coming from? A general consultation is a good starting "
            "point for most bone, joint and movement concerns."
        ),
        overview=(
            "Many people put off seeing a doctor because they are unsure whether their pain is "
            "serious enough. A general orthopaedic consultation gives you time to describe what "
            "you are experiencing and to have it assessed properly.",
            "The aim is to understand what may be causing your symptoms and to explain your "
            "options in plain language, so you can make informed decisions about your care.",
        ),
        signs=(
            "Pain or stiffness that has lasted more than a few weeks",
            "Discomfort that affects sleep, work or daily routines",
            "Reduced movement in a joint or the back",
            "Questions about an old injury that still troubles you",
        ),
        consultation=_CONSULT_COMMON,
        featured=True,
    ),
    Service(
        slug="bone-and-fracture-care",
        title="Bone and Fracture Care",
        short="Assessment and guidance for suspected fractures and bone injuries.",
        icon="bone",
        summary="Falls, accidents and sports can injure bones. Early assessment helps guide safe recovery.",
        overview=(
            "A fracture is a break or crack in a bone. It can happen after a fall, an accident or "
            "a sports injury, and sometimes with less force when bones are weaker.",
            "If you think you may have injured a bone, an orthopaedic assessment can help confirm "
            "what has happened and guide the next steps for healing.",
        ),
        signs=(
            "Pain, swelling or bruising after a fall or injury",
            "Difficulty putting weight on a leg or using an arm",
            "A limb that looks out of shape",
            "Pain that continues long after an old injury",
        ),
        consultation=_CONSULT_COMMON,
        anatomy=("shoulder", "hip", "ankle"),
    ),
    Service(
        slug="joint-pain-evaluation",
        title="Joint Pain Evaluation",
        short="Understanding the cause of aching, stiff or swollen joints.",
        icon="joint",
        summary="Joint pain has many possible causes. A clinical evaluation helps make sense of yours.",
        overview=(
            "Joints allow us to bend, twist and move freely. When a joint becomes painful, stiff or "
            "swollen, everyday activities can start to feel difficult.",
            "Joint pain can have many causes, including wear and tear, injury or inflammation. "
            "An evaluation helps identify what may be contributing to your symptoms.",
        ),
        signs=(
            "Morning stiffness that takes time to ease",
            "Swelling, warmth or tenderness around a joint",
            "Pain that worsens with activity or after rest",
            "Clicking, catching or a feeling of instability",
        ),
        consultation=_CONSULT_COMMON,
        anatomy=("shoulder", "hip", "knee", "ankle"),
    ),
    Service(
        slug="knee-and-hip-concerns",
        title="Knee and Hip Concerns",
        short="Help for pain that affects walking, stairs and getting up from a chair.",
        icon="knee",
        summary="Knee and hip pain can make walking and climbing stairs harder. Assessment is the first step.",
        overview=(
            "The knees and hips carry much of your body weight with every step. Pain in these "
            "joints can affect walking, climbing stairs, sitting cross-legged or getting up from "
            "a chair.",
            "A consultation can help understand why the pain is happening and what may help you "
            "stay active and comfortable.",
        ),
        signs=(
            "Pain while walking, climbing stairs or squatting",
            "Stiffness after sitting for a while",
            "Swelling around the knee",
            "Pain in the groin, thigh or buttock",
        ),
        consultation=_CONSULT_COMMON,
        anatomy=("hip", "knee"),
    ),
    Service(
        slug="back-and-spine-concerns",
        title="Back and Spine Concerns",
        short="Evaluation of back and neck pain that affects sitting, standing and work.",
        icon="spine",
        summary="Back and neck pain are very common. Understanding the cause helps you move with more confidence.",
        overview=(
            "Your spine supports your body and protects the nerves that run through it. Back and "
            "neck pain can come from muscles, joints, discs or nerves, and can affect sitting, "
            "standing, sleeping and work.",
            "A careful evaluation helps identify possible causes and the appropriate next steps.",
        ),
        signs=(
            "Lower back or neck pain lasting more than a few weeks",
            "Pain that spreads into the arm or leg",
            "Stiffness that limits bending or turning",
            "Numbness or tingling in the hands or feet",
        ),
        consultation=_CONSULT_COMMON,
        anatomy=("spine",),
    ),
    Service(
        slug="sports-and-movement-injuries",
        title="Sports and Movement-Related Injuries",
        short="Assessment of sprains, strains and injuries from sport or exercise.",
        icon="movement",
        summary="Injured during sport or exercise? Assessment helps guide a safe return to activity.",
        overview=(
            "Sprains, strains and other injuries can happen during sport, exercise or everyday "
            "activity. Some settle quickly, while others need a closer look.",
            "An orthopaedic assessment can help understand the injury and guide a safe, gradual "
            "return to the activities you enjoy.",
        ),
        signs=(
            "Pain or swelling after a twist, fall or impact",
            "A joint that feels loose or gives way",
            "Pain that returns every time you exercise",
            "Reduced strength or range of movement",
        ),
        consultation=_CONSULT_COMMON,
        anatomy=("shoulder", "knee", "ankle"),
    ),
)

SERVICES_BY_SLUG = {s.slug: s for s in SERVICES}


def get_service(slug: str) -> Service | None:
    return SERVICES_BY_SLUG.get(slug)
