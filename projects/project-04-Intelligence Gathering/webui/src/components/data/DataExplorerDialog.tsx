import { useState } from 'react'
import { Database } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { DataExplorer } from './DataExplorer'

export function DataExplorerDialog() {
  const [open, setOpen] = useState(false)
  return <Dialog open={open} onOpenChange={setOpen}>
    <DialogTrigger asChild>
      <Button variant="ghost" size="sm" className="h-7 px-2 text-[#8b949e] hover:text-[#00ffff] hover:bg-[#00ffff]/10" title="查看采集结果">
        <Database className="w-4 h-4" />
      </Button>
    </DialogTrigger>
    <DialogContent className="max-h-[86vh] max-w-6xl overflow-auto">
      <DialogHeader>
        <DialogTitle>采集结果</DialogTitle>
        <DialogDescription>浏览、预览和下载本地采集文件。</DialogDescription>
      </DialogHeader>
      <DataExplorer compact />
    </DialogContent>
  </Dialog>
}
