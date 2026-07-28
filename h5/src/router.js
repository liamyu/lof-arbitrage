import { createRouter, createWebHashHistory } from 'vue-router'
import Opportunities from './views/Opportunities.vue'
import FundDetail from './views/FundDetail.vue'
import DataStatus from './views/DataStatus.vue'

const routes = [
  { path: '/', redirect: '/opportunities' },
  { path: '/opportunities', component: Opportunities },
  { path: '/fund/:code', component: FundDetail },
  { path: '/status', component: DataStatus }
]

export default createRouter({
  history: createWebHashHistory(),
  routes
})
