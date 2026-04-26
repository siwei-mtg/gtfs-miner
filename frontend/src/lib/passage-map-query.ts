/**
 * Shared helpers for building the query string sent to /map/passage-ag and
 * /map/passage-arc.  Both endpoints accept the same optional filters:
 *   - ligne_ids      : "1,2,3"
 *   - sous_ligne_keys: "1:A,1:B,2:R"  (id_ligne_num:sous_ligne)
 *
 * Both filters are AND-ed with jour_type on the backend.  Empty arrays mean
 * "no filter" and are simply omitted from the URL.
 *
 * Sous-ligne values are assumed to be ASCII identifiers (typical: "A", "B",
 * "R", "1A").  Commas inside a sous_ligne value will break the parser — this
 * is documented as a known edge case in the design plan.
 */
export interface SousLigneKey {
  id_ligne_num: number
  sous_ligne: string
}

export function buildPassageMapQuery(params: {
  jourType: number
  ligneIds?: number[]
  sousLigneKeys?: SousLigneKey[]
  splitBy?: 'none' | 'route_type'
}): string {
  const parts: string[] = [`jour_type=${params.jourType}`]
  if (params.splitBy) {
    parts.push(`split_by=${params.splitBy}`)
  }
  if (params.ligneIds && params.ligneIds.length > 0) {
    parts.push(`ligne_ids=${params.ligneIds.join(',')}`)
  }
  if (params.sousLigneKeys && params.sousLigneKeys.length > 0) {
    const encoded = params.sousLigneKeys
      .map((k) => `${k.id_ligne_num}:${encodeURIComponent(k.sous_ligne)}`)
      .join(',')
    parts.push(`sous_ligne_keys=${encoded}`)
  }
  return parts.join('&')
}
