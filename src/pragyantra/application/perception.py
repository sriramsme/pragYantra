"""Turn provider interpretations into observations without losing source timing."""

from pragyantra.application.interfaces import VisionProvider
from pragyantra.application.models import (
    ImageFrame,
    PreviousSceneContext,
    VisualObservation,
)


async def perceive_image(
    image: ImageFrame,
    provider: VisionProvider,
    *,
    previous: PreviousSceneContext | None = None,
) -> VisualObservation:
    if previous is not None:
        previous.validate_for(source=image.source, observed_at=image.observed_at)
        description = await provider.describe(image, previous=previous)
    else:
        description = await provider.describe(image)
    return VisualObservation(
        source=image.source,
        observed_at=image.observed_at,
        description=description.text,
        provider=description.provider,
        model=description.model,
        image_detail=description.image_detail,
        previous_context=previous,
    )
