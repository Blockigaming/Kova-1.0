"""Immutable upstream source references, not downloaded or active model identities.

Pins were checked against the official Qwen commit pages on 2026-09-18. This
module has no loader, network, authorization, job dispatch or resource API. A
reference identifies upstream source; derivative quantization/fine-tuning needs
its own artifact digest and verified lineage before serving.
"""
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class ModelSourceReference:
    slot: str
    model: str
    revision: str

    @property
    def source_url(self):
        return f'https://huggingface.co/{self.model}/commit/{self.revision}'


MODEL_SOURCE_REFERENCES = MappingProxyType({
    'chat-shared': ModelSourceReference(
        'chat-shared', 'Qwen/Qwen3-8B',
        'b968826d9c46dd6066d109eabc6255188de91218'),
    'work-cosmo': ModelSourceReference(
        'work-cosmo', 'Qwen/Qwen3-0.6B',
        'c1899de289a04d12100db370d81485cdf75e47ca'),
    'work-orion': ModelSourceReference(
        'work-orion', 'Qwen/Qwen3-1.7B',
        '70d244cc86ccca08cf5af4e1e306ecf908b1ad5e'),
    'work-nova': ModelSourceReference(
        'work-nova', 'Qwen/Qwen3-4B',
        '1cfa9a7208912126459214e8b04321603b3df60c'),
})
CHAT_SOURCE_ROUTES = ('instant', 'medium', 'high', 'extra-high', 'max', 'ultra')
WORK_SOURCE_EFFORTS = ('light', 'medium', 'high', 'extra-high', 'max', 'ultra')
ROUTE_MODEL_SLOTS = MappingProxyType({
    **{route: 'chat-shared' for route in CHAT_SOURCE_ROUTES},
    **{f'work:{family}:{effort}': f'work-{family}'
       for family in ('cosmo', 'orion', 'nova') for effort in WORK_SOURCE_EFFORTS},
})


def source_reference_for_route(route_id):
    """Return only the pinned source contract of an already canonical route.

    This grants no tier entitlement, model execution or download permission.
    Auto is deliberately not a 25th model: the existing trusted classifier must
    first resolve it to an allowed Chat route. Alias normalization belongs to
    the versioned selection boundary, not to model-identity lookup.
    """
    if type(route_id) is not str or route_id not in ROUTE_MODEL_SLOTS:
        raise ValueError('model source route rejected')
    return MODEL_SOURCE_REFERENCES[ROUTE_MODEL_SLOTS[route_id]]
