# Current Kova model topology

Owner policy source: Models issue #10 comment 5734534302.

## Chat

Chat has one underlying model slot, `chat-shared`. Lite, Medium, Thinking/High,
Extra High, Max, and Ultra are effort/orchestration choices over that same model.
They may change bounded private passes, latency/depth, and truthful progress
behavior, but must not silently select different base weights.

Lite is the default. Free and signed-out users remain locked to Lite. Plus exposes
Lite, Medium, Thinking. Pro exposes Lite, Medium, High, Extra High, Max, Ultra.
Chat Ultra uses the same model slot through bounded 2-5 specialist orchestration.

No upstream Chat model is selected by this source. That remains a benchmark/runtime
decision and must be bound to a pinned revision before execution can be called
integrated.

## Work

Work has three distinct underlying model slots:
- Kova 5.6 Cosmo -> `work-cosmo`
- Kova 5.6 Orion -> `work-orion`
- Kova 5.6 Nova -> `work-nova`

The three slots must represent distinct Work models. Within one family, Lite,
Medium, High, Extra High, Max, and Ultra stay on that family's model. The effort
controls bounded work depth; it does not change family identity. Ultra remains
bounded sub-agent orchestration over that same selected family model.

The historical internal route id `light` is retained for compatibility while
the product label is Lite.

## Usage

Paid Chat is not debited from the Work weekly allowance. Work remains weekly.
Pro capacity remains five times Plus. An exhausted Work allowance does not disable
paid Chat. Paid replenishment is allowed by product policy, but its amount, price,
Plus base allowance, and reset anchor are intentionally null until explicitly
specified.

## Current implementation gap

The existing runtime still maps Chat efforts to Cosmo/Orion/Nova profiles and
models Work families as behavior contracts over one shared Core candidate. The
validator reports those mismatches rather than declaring the newest policy live.
It also reports all four upstream model slots unselected. No deployment, model
download, paid benchmark, quota value, reset time, or replenishment price is
created by this source.
