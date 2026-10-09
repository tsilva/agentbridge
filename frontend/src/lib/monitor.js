// Python offsets count Unicode code points, while JavaScript strings count UTF-16 units.
export const streamOffset = text => Array.from(text || '').length;
export function needsDetailRefresh(detail, requests) {
  return !!detail?.is_active && !requests.some(request => request.request_id === detail.request_id && request.is_active);
}
export function filteredRequests(requests, filter) {
  const query = filter.trim().toLowerCase();
  return requests.filter(request => [request.request_id, request.model, request.is_active ? 'streaming' : request.error ? 'error' : 'ok', request.error || ''].join(' ').toLowerCase().includes(query));
}
