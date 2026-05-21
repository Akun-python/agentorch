from __future__ import annotations

from collections.abc import Callable

from ...api.config import GraphMemoryConfig
from ...api.models import ExperienceCandidate, PromotionComponentScores, PromotionDecision, PromotionReport
from .ingestion import CapsuleIngestionService


class CapsulePromotionService:
    """候选经验提升为长期胶囊的独立服务。"""

    def __init__(
        self,
        *,
        config: GraphMemoryConfig,
        ingestion_service: CapsuleIngestionService,
        score_builder: Callable[[ExperienceCandidate], PromotionComponentScores] | None = None,
    ) -> None:
        self.config = config
        self.ingestion_service = ingestion_service
        self.score_builder = score_builder or self._default_score_builder

    def promote_candidates(self, candidates: list[ExperienceCandidate]) -> PromotionReport:
        """筛选并写入达到阈值的候选经验。"""

        if not candidates:
            return PromotionReport()

        promoted_capsules = []
        decisions: list[PromotionDecision] = []
        for candidate in candidates:
            scores = self.score_builder(candidate)
            total = self._compose_total_score(scores)
            promoted = total >= self.config.promotion_threshold
            reasons = self._build_reasons(candidate, scores=scores, promoted=promoted)
            capsule_id = candidate.experience_id if promoted else None
            decisions.append(
                PromotionDecision(
                    experience_id=candidate.experience_id,
                    promoted=promoted,
                    total_score=round(total, 4),
                    threshold=self.config.promotion_threshold,
                    scores=scores,
                    capsule_id=capsule_id,
                    reasons=reasons,
                )
            )
            if promoted:
                promoted_capsules.append(candidate.to_memory_capsule(capsule_id=candidate.experience_id))

        stored_ids = self.ingestion_service.store_capsules(promoted_capsules) if promoted_capsules else []
        return PromotionReport(
            total_candidates=len(candidates),
            promoted_count=len(promoted_capsules),
            skipped_count=len(candidates) - len(promoted_capsules),
            stored_capsule_ids=stored_ids,
            decisions=decisions,
        )

    def _compose_total_score(self, scores: PromotionComponentScores) -> float:
        """按配置权重合成晋升总分。"""

        return (
            self.config.promotion_val_weight * scores.val_score
            + self.config.promotion_reuse_weight * scores.reuse_score
            + self.config.promotion_out_weight * scores.out_score
            + self.config.promotion_gen_weight * scores.gen_score
            - self.config.promotion_noise_weight * scores.noise_score
        )

    def _default_score_builder(self, candidate: ExperienceCandidate) -> PromotionComponentScores:
        """默认晋升评分由价值、复用、结果、泛化和噪声构成。"""

        return PromotionComponentScores(
            val_score=self._value_score(candidate),
            reuse_score=self._reuse_score(candidate),
            out_score=self._outcome_score(candidate),
            gen_score=self._generalization_score(candidate),
            noise_score=self._noise_score(candidate),
        )

    def _value_score(self, candidate: ExperienceCandidate) -> float:
        """评价经验是否有验证、证据和结构化主张支撑。"""

        status_boost = {
            "validated": 1.0,
            "active": 0.9,
            "candidate": 0.5,
            "deprecated": 0.1,
        }.get(candidate.status, 0.4)
        evidence_bonus = min(1.0, len(candidate.evidence_refs) / max(1, self.config.promotion_min_evidence_refs))
        claim_bonus = min(1.0, len(candidate.claims) / 2.0)
        return round(min(1.0, 0.45 * status_boost + 0.35 * evidence_bonus + 0.20 * claim_bonus), 4)

    def _reuse_score(self, candidate: ExperienceCandidate) -> float:
        """复用次数越多，越可能值得晋升。"""

        if candidate.reuse_count <= 0:
            return 0.0
        return round(min(1.0, candidate.reuse_count / 3.0), 4)

    def _outcome_score(self, candidate: ExperienceCandidate) -> float:
        """判断 outcome 是否具备可执行结果。"""

        outcome_text = " ".join([candidate.summary, candidate.outcome]).lower()
        keyword_hits = sum(1 for item in self.config.promotion_result_keywords if item in outcome_text)
        has_outcome = 1.0 if candidate.outcome.strip() else 0.0
        return round(min(1.0, 0.6 * has_outcome + 0.15 * keyword_hits), 4)

    def _generalization_score(self, candidate: ExperienceCandidate) -> float:
        """估计经验跨任务复用的可能性。"""

        scope_span = min(1.0, len(set(candidate.knowledge_scope)) / 3.0)
        tag_span = min(1.0, len(set(candidate.tags)) / 4.0)
        family_bonus = 0.5 if candidate.task_family else 0.0
        return round(min(1.0, 0.4 * scope_span + 0.3 * tag_span + 0.3 * family_bonus), 4)

    def _noise_score(self, candidate: ExperienceCandidate) -> float:
        """低置信、空摘要、缺证据都会增加噪声惩罚。"""

        empty_summary_penalty = 0.5 if not candidate.summary.strip() else 0.0
        low_confidence_penalty = max(0.0, 1.0 - float(candidate.confidence))
        missing_evidence_penalty = 0.35 if not candidate.evidence_refs else 0.0
        return round(min(1.5, empty_summary_penalty + low_confidence_penalty + missing_evidence_penalty), 4)

    def _build_reasons(
        self,
        candidate: ExperienceCandidate,
        *,
        scores: PromotionComponentScores,
        promoted: bool,
    ) -> list[str]:
        """生成中文晋升/跳过原因，便于用户直接阅读。"""

        reasons: list[str] = []
        if scores.val_score >= 0.7:
            reasons.append("证据与验证信号较强")
        if scores.reuse_score > 0:
            reasons.append("存在历史复用信号")
        if scores.out_score >= 0.6:
            reasons.append("结果表述具备可执行性")
        if scores.gen_score >= 0.5:
            reasons.append("具备跨任务泛化价值")
        if scores.noise_score >= 0.8:
            reasons.append("噪声或低置信惩罚较高")
        if not reasons:
            reasons.append("分项信号整体一般")
        if promoted:
            reasons.append(f"总分达到阈值 {self.config.promotion_threshold:.2f}")
        else:
            reasons.append(f"总分未达到阈值 {self.config.promotion_threshold:.2f}")
        return reasons
