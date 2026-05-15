import { AbilityComponent } from '@ohos/ability'

@Entry
@Component
struct ${Feature}Ability {
  @State list: any[] = []
  @State loading: boolean = false
  @State hasMore: boolean = true

  aboutToAppear() {
    this.loadData()
  }

  async loadData() {
    if (this.loading || !this.hasMore) return
    
    this.loading = true
    try {
      const response = await fetch('/api/${feature}')
      const data = await response.json()
      
      this.list = [...this.list, ...data]
      this.hasMore = data.length >= 20
    } catch (error) {
      prompt.showToast({ message: '加载失败' })
    } finally {
      this.loading = false
    }
  }

  build() {
    Column() {
      if (this.loading && this.list.length === 0) {
        Text('加载中...')
          .fontSize(14)
          .fontColor('#999')
          .padding(32)
      } else if (this.list.length === 0) {
        Text('暂无数据')
          .fontSize(14)
          .fontColor('#999')
          .padding(32)
      } else {
        List() {
          ForEach(this.list, (item: any) => {
            ListItem() {
              Text(item.name)
                .fontSize(16)
                .padding(12)
            }
            .onClick(() => this.handleSelect(item))
          })
        }
        .divider({ strokeWidth: 1, color: '#eee' })
        .onReachEnd(() => this.loadData())
      }
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#fff')
  }

  handleSelect(item: any) {
    router.pushUrl({
      url: 'pages/${feature}/Detail',
      params: { id: item.id }
    })
  }
}
