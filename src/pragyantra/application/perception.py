"""Turn provider interpretations into observations without losing source timing."""

from pragyantra.application.interfaces import VisionProvider
from pragyantra.application.models import ImageFrame, VisualObservation


async def perceive_image(
    image: ImageFrame, provider: VisionProvider
) -> VisualObservation:
    description = await provider.describe(image)
    return VisualObservation(
        source=image.source,
        observed_at=image.observed_at,
        description=description.text,
        provider=description.provider,
        model=description.model,
        image_detail=description.image_detail,
    )
