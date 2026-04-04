import client from './client';
import type { InsightsResponse, RecommendationRequest, RecommendationResponse } from '../types';

export async function fetchInsights(): Promise<InsightsResponse> {
    const res = await client.get<InsightsResponse>('/insights');
    return res.data;
}

export async function fetchRecommendations(
    req: RecommendationRequest,
): Promise<RecommendationResponse> {
    const res = await client.post<RecommendationResponse>('/recommendations', req);
    return res.data;
}