# Memo: learning Reachy Mini's head wobble from human data

Date: 2026-09-12. For Rémi Fabre. Feasibility study only, nothing was trained.

## Headline

Feasible, and cheaper than it sounds. The head-pose sub-problem is tiny (3 angles at 20 Hz), the data exists under usable licences, and a streaming GRU of under 1 M parameters runs on the CM4 with room to spare. The real risks are not compute: they are licence hygiene, retargeting to a Stewart platform, and the fact that even the best academic systems still score barely above chance on "is this motion appropriate for this speech" (GENEA 2023). Supervised imitation plus a preference step on filmed A/B pairs is the sensible first target. Full RL is optional, not required.

## 1. Datasets with speech and head motion

| Dataset | Size | Head pose | Style | Licence (as found) |
|---|---|---|---|---|
| BEAT2 (EMAGE) | 60 h, 25 speakers, mocap SMPL-X + FLAME | explicit, neck and head joints | studio, semi-acted, 8 emotions | Apache-2.0 on the HF page |
| Talking With Hands / GENEA 2023 | 18 h dyadic mocap, BVH | explicit | spontaneous conversation | not verified |
| HDTF + TFHP (DiffPoseTalk) | 15.8 h + 26.5 h, FLAME params fitted | reconstructed | lectures, news, interviews | HDTF CC BY 4.0, TFHP by request form |
| Learning to Listen | 72 h dyadic, 3D annotations | reconstructed (DECA) | in the wild | not verified, YouTube-derived |
| TalkingHead-1KH | ~1000 h raw YouTube | none, must extract | in the wild | videos CC BY 3.0, scripts MIT |
| VoxCeleb2 | 140 k YouTube clips | none, must extract | in the wild | metadata CC BY-SA 4.0, videos are YouTube |
| PATS | 251 h, 25 speakers, 2D OpenPose | 2D only | TV hosts, lecturers | CC BY-NC |
| TalkVid (2025) | 1244 h, 7729 speakers | none | in the wild | CC BY-NC 4.0 |
| MEAD, VOCASET | 60 acted speakers; 0.5 h | MEAD none, VOCASET yes | acted | MEAD research agreement, too small |

Practical reading: BEAT2 gives clean, explicit head rotations and covers emotions, which matches the "emotional colouring" idea. HDTF plus TalkingHead-1KH give in-the-wild dynamics under CC BY. NC-licensed sets (PATS, TalkVid) are fine for a study, not for a model shipped in the product. I could not verify the exact BEAT2 dataset licence beyond the HF tag; the original BEAT was non-commercial, so check before shipping.

## 2. Extracting head pose from video yourself

- MediaPipe Face Landmarker (Apache-2.0) returns a 4x4 head transformation matrix per frame, about 100 fps on a laptop CPU. One hour of 25 fps video is about 15 to 20 CPU-minutes. Accuracy in degrees is not published; expect a few degrees of bias and frame jitter, which matter less than dynamics for our use: we need velocities and onset timing, not absolute angles.
- 3DDFA_V2 reports 4.3 degrees mean error on AFLW2000-3D; 3DDFA-V3 (CVPR 2024) ships a MobileNet-V3 fast variant. OpenFace 2 was measured at 14.1 degrees on BIWI in one benchmark: avoid.
- DECA and EMOCA (FLAME fitters) are non-commercial licences. FLAME 2023 itself is CC BY 4.0. Prefer MediaPipe or 3DDFA for a product pipeline.
- Rights: YouTube's ToS position is contested (Google says the ToS allows training, its CEO said the opposite to OpenAI, creators are suing Snap). In the EU, DSM directive art. 4 allows text and data mining by companies unless the rightholder opted out in machine-readable form; art. 3 is for research organisations. Safest path: restrict to CC BY subsets (TalkingHead-1KH, HDTF) plus mocap (BEAT2), keep the video URLs and licence tags with the extracted poses.

## 3. Prior work on head motion from speech

- Small models already work: Ding et al. 2015 used a BLSTM on 26-D log Mel filterbanks; Busso reported sentence-level correlation of about 0.8 between MFCCs and head motion. Audio2Head (2021) uses a motion-aware RNN for 6-D head pose. SadTalker's PoseVAE is a conditional VAE for pose style. DiffPoseTalk (2024) is a diffusion model with a style encoder trained on TFHP. Learning to Listen uses a VQ-VAE for listener head motion. EMAGE covers full-body on BEAT2.
- VASA-1, EMO, Hallo, Teller generate video with diffusion; the head-motion part lives in their latent, far too heavy for the CM4 and not separable without their code.
- GENEA 2023 (12 systems): a few systems match mocap on human-likeness, but appropriateness to the speech stays in a narrow band slightly above chance; FGD was the best objective proxy (Kendall tau around -0.5).
- CM4 budget: the current v4 already runs an FFT every 50 ms at 0.1 % of a core. A causal GRU or TCN with 0.3 to 1 M parameters on the same 20 Hz features costs well under 1 ms per step in ONNX on the CM4 (estimate, not measured). Note that in the skit pipeline the audio is TTS known in advance, so lookahead is free offline; only the live streaming case is bound to 50 ms.

## 4. Transfer to Reachy Mini

- Workspace: pitch and roll clamp at ±40 degrees, head yaw ±180 with body-head difference under ±65. Conversational head motion is mostly inside ±15 degrees, so amplitude fits; the wobbler already emits pitch/yaw/roll plus mm translations at 20 Hz. Retarget with a per-axis gain, a velocity clamp (Placo IK limits joints at 13 rad/s) and a low-pass to hide Stewart coupling. MuJoCo sim checks reachability and saturation before any robot runs.
- Relevant robotics precedents: an imitation pipeline giving NAO human-like head motion (arXiv 2407.11915) and PhysDrift (June 2026), which shows naive retargeting loses diversity and sync and proposes IK-based retargeting that keeps prosody alignment.
- Imitation then RL here means: supervised model first, then optimise the lab's own metrics (stillness_in_silence, onset_alignment), FGD against human pose statistics, and a preference model fitted on the community A/B votes. RL adds value only for non-differentiable rewards and robot-native constraints; the risk is reward hacking (twitching at every onset). A DPO-style preference step on pairs of rendered clips is likely enough and far simpler.

## 5. Three plans

| | Small | Medium | Large |
|---|---|---|---|
| Idea | distil v5 plus human head-pose statistics into a tiny model, keep an emotion input | streaming GRU/TCN trained on extracted poses | diffusion or VQ (DiffPoseTalk-like) then distil to a causal student |
| Data | 5 to 15 h, BEAT2 head channel plus HDTF | 20 to 50 h: BEAT2 + HDTF + CC BY slice of TalkingHead-1KH, MediaPipe extraction (10 to 20 CPU-hours) | 50 to 100 h, same sources plus TFHP by request |
| Compute | CPU or 1 to 3 GPU-hours | 5 to 20 GPU-hours (one A100 afternoon) | 100 to 300 GPU-hours plus 10 for distillation |
| Calendar | 2 weeks | 4 to 6 weeks | 2 to 3 months |
| Risk | may only reproduce v5 | pose noise, average-motion collapse (mitigate with FGD and velocity histogram losses) | licence and rights review, student loses diversity |
| Evaluation | offline: stillness_in_silence, onset_alignment, FGD, velocity histogram; online: the planned filmed-robot community A/B | same | same, plus style-conditioned tests |

## 6. Open questions for discussion

- Product or study: do we need shippable licences from day one (excludes PATS, TalkVid, DECA/EMOCA)?
- Target style: real conversational head motion is subtle; do we want a faithful imitation or an amplified, cartoon version, and is that a post-gain or a training target?
- Is emotion an input label (BEAT2 style) or inferred from the voice?
- Do we accept a non-causal model for skits and a causal one for live chat, or one causal model everywhere?
- How many A/B votes can the community realistically give, since that decides whether preference tuning is viable?

Sources: BEAT2 (https://huggingface.co/datasets/H-Liu1997/BEAT2, https://is.mpg.de/ps/projects/beat2-dataset-for-holistic-co-speech-gesture-generation), GENEA 2023 (https://arxiv.org/abs/2308.12646), Talking With Hands (https://ieeexplore.ieee.org/document/9010909/), DiffPoseTalk and TFHP (https://github.com/DiffPoseTalk/DiffPoseTalk), HDTF (https://github.com/MRzzm/HDTF), Learning to Listen (https://arxiv.org/abs/2204.08451), TalkingHead-1KH (https://github.com/tcwang0509/TalkingHead-1KH), VoxCeleb2 (https://www.robots.ox.ac.uk/~vgg/data/voxceleb/vox2.html), PATS (https://github.com/chahuja/pats), TalkVid (https://github.com/FreedomIntelligence/TalkVid), MediaPipe (https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker), 3DDFA-V3 (https://github.com/wang-zidu/3DDFA-V3), 3DDFA_V2 accuracy (https://arxiv.org/pdf/2407.05357), EMOCA licence (https://emoca.is.tue.mpg.de/license.html), FLAME (https://flame.is.tue.mpg.de/), YouTube ToS dispute (https://variety.com/2026/digital/news/google-youtube-terms-of-service-train-ai-models-lawsuit-1236771486/, https://techcrunch.com/2026/01/26/youtubers-sue-snap-for-alleged-copyright-infringement-in-training-its-ai-models), EU TDM exceptions (https://legalblogs.wolterskluwer.com/copyright-blog/the-new-copyright-directive-text-and-data-mining-articles-3-and-4/), Ding 2015 BLSTM (https://www.isca-archive.org/interspeech_2015/ding15_interspeech.pdf), Audio2Head (https://arxiv.org/abs/2107.09293), SadTalker (https://arxiv.org/abs/2211.12194), VASA-1 (https://arxiv.org/abs/2404.10667v2), NAO head imitation (https://arxiv.org/abs/2407.11915), PhysDrift (https://arxiv.org/abs/2606.19935), Reachy Mini limits (https://huggingface.co/docs/reachy_mini/platforms/reachy_mini/hardware).
