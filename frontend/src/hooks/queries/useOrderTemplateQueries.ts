import { useQuery } from '@tanstack/react-query'

import { listOrderTemplates } from '../../api/orderTemplatesApi'
import type { OrderTemplateListResponse } from '../../api/orderTemplatesApi'
import { queryKeys } from '../../lib/queryClient'

export function useOrderTemplates(workspaceId?: string, enabled = true) {
  return useQuery<OrderTemplateListResponse>({
    queryKey: queryKeys.orderTemplates.list(workspaceId),
    queryFn: () =>
      listOrderTemplates({
        workspace_id: workspaceId,
        limit: 500,
      }),
    enabled: enabled && Boolean(workspaceId),
    staleTime: 1000 * 60,
  })
}
