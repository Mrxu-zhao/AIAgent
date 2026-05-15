Page({
  data: {
    list: [],
    loading: false,
    hasMore: true
  },

  onLoad(options) {
    this.loadData()
  },

  async loadData() {
    if (this.data.loading || !this.data.hasMore) return
    
    this.setData({ loading: true })
    try {
      const res = await wx.request({
        url: '/api/${feature}',
        method: 'GET'
      })
      
      if (res.statusCode === 200) {
        this.setData({
          list: [...this.data.list, ...res.data],
          hasMore: res.data.length >= 20,
          loading: false
        })
      } else {
        throw new Error('请求失败')
      }
    } catch (error) {
      wx.showToast({ title: '加载失败', icon: 'error' })
      this.setData({ loading: false })
    }
  },

  onItemTap(e) {
    const item = e.currentTarget.dataset.item
    wx.navigateTo({
      url: `/pages/${feature}/detail?id=${item.id}`
    })
  },

  onReachBottom() {
    this.loadData()
  },

  onPullDownRefresh() {
    this.setData({ list: [], hasMore: true })
    this.loadData().then(() => {
      wx.stopPullDownRefresh()
    })
  }
})
