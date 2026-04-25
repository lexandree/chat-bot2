"""Repository for reviewable observation claims."""

from __future__ import annotations


class ClaimRepository:
    def __init__(self) -> None:
        self._claims: dict[str, dict[str, object]] = {}
        self._candidate_entities: dict[str, dict[str, object]] = {}
        self._candidate_claims: dict[str, dict[str, object]] = {}
        self._proposition_candidates: dict[str, dict[str, object]] = {}
        self._proposition_supports: dict[str, dict[str, object]] = {}

    def save(self, claim: dict[str, object]) -> dict[str, object]:
        self._claims[str(claim["claim_id"])] = claim
        return claim

    def get(self, claim_id: str) -> dict[str, object] | None:
        return self._claims.get(claim_id)

    def save_candidate_entity(self, entity: dict[str, object]) -> dict[str, object]:
        self._candidate_entities[str(entity["candidate_entity_id"])] = entity
        return entity

    def save_candidate_claim(self, claim: dict[str, object]) -> dict[str, object]:
        self._candidate_claims[str(claim["candidate_claim_id"])] = claim
        return claim

    def get_candidate_claim(self, candidate_claim_id: str) -> dict[str, object] | None:
        return self._candidate_claims.get(candidate_claim_id)

    def list_candidate_claims(self) -> list[dict[str, object]]:
        return list(self._candidate_claims.values())

    def save_proposition_candidate(
        self,
        candidate: dict[str, object],
    ) -> dict[str, object]:
        self._proposition_candidates[str(candidate["proposition_candidate_id"])] = candidate
        return candidate

    def get_proposition_candidate(
        self,
        proposition_candidate_id: str,
    ) -> dict[str, object] | None:
        return self._proposition_candidates.get(proposition_candidate_id)

    def list_proposition_candidates(self) -> list[dict[str, object]]:
        return list(self._proposition_candidates.values())

    def save_proposition_support(
        self,
        support: dict[str, object],
    ) -> dict[str, object]:
        self._proposition_supports[str(support["support_id"])] = support
        return support

    def list_proposition_supports(self) -> list[dict[str, object]]:
        return list(self._proposition_supports.values())
