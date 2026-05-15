import React, { useState, useCallback } from 'react'
import './${ComponentName}.css'

interface ${ComponentName}Props {
  data?: any[]
  loading?: boolean
  onUpdate?: (value: any) => void
  onSelect?: (item: any) => void
}

export const ${ComponentName}: React.FC<${ComponentName}Props> = ({
  data = [],
  loading = false,
  onUpdate,
  onSelect,
}) => {
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const handleSelect = useCallback((item: any) => {
    setSelectedId(item.id)
    onSelect?.(item)
  }, [onSelect])

  if (loading) {
    return <div className="${componentName}-loading">加载中...</div>
  }

  if (!data.length) {
    return <div className="${componentName}-empty">暂无数据</div>
  }

  return (
    <div className="${componentName}-container">
      {data.map(item => (
        <div
          key={item.id}
          className={`${componentName}-item ${selectedId === item.id ? 'selected' : ''}`}
          onClick={() => handleSelect(item)}
        >
          {item.name}
        </div>
      ))}
    </div>
  )
}
