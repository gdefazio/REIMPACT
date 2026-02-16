library(ggplot2)
library(reshape2)
library(openxlsx)

exdir = "/Users/giuseppedefazio/Documents/RTDA_UniBA/progetti/ELIXIR_citations/out_of_github/Serv_Deliv_Plan_citations/gen26/scopus_openalex/SDP_impact.xlsx"

#### FIGURE 1 ####
citations = read.xlsx(exdir, sheet = 1, rowNames = T,cols = c(1,4,6,8))
citations = aggregate( . ~ Platform, citations, sum)
melt.citations = melt(citations, id.vars = "Platform")
plus = aggregate(value ~ variable, melt.citations, sum)
plus$Platform = 'Total'
melt.citations = rbind(melt.citations, plus)

ggplot(melt.citations, aes(x=Platform, y=value, fill=variable))+
  geom_bar(stat = "identity", position = 'dodge') +
  scale_x_discrete(limits=melt.citations$Platform[order(melt.citations$value)],
                   expand = expansion(add = c(1,0)))+
  scale_fill_manual(labels=c('OpenAlex', 'Scopus'),
                    values = c('orange2', 'cornflowerblue'),
                    breaks = c('OpenAlexCitations', 'PyBlioCitations'))+
  scale_y_log10('Citations',labels=scales::comma, expand = expansion(add = c(0.07,0.2)))+
  
  geom_text(aes(label=scales::comma(value)),vjust = -.5, 
            position = position_dodge2(width = 1.8)) +
  theme(legend.title = element_blank(),
        panel.background = element_blank(),
        axis.line = element_line(colour = 'grey19'),
        axis.text = element_text(face = 'bold', size=11),
        axis.title=element_text(face = 'bold.italic', size=10),
        legend.text = element_text(face = 'bold.italic', size=10))

#### FIGURE 2 ####
citdf = read.xlsx(exdir, sheet = 1, rowNames = T,cols = c(1,2,6,7,8))
citdf1 = citdf
citdf1$Service = 'Total'
plus = agcitdfplus = aggregate(. ~ Service, citdf1, sum)
rm(citdf1)
citdf = rbind(citdf,plus)
rm(plus)
citdf = citdf[order(citdf$OpenAlexCitations, decreasing = T),]
citdf.h = head(citdf, 11)
m.citdf.h = melt(citdf.h, id.vars = 'Service')
m.citdf.h$variable = factor(m.citdf.h$variable,levels = c('OpenAlexCitations', 'PyBlioCitations','OpenAlexCitationsOfCiting'),
       labels = 1:3)

pos <- position_dodge2(width = 0.9,reverse = TRUE)
ggplot(m.citdf.h, aes(x=value, y=Service, fill=variable))+
  geom_bar(stat = "identity", position = pos) +
  scale_y_discrete(limits=citdf.h$Service,
                   expand = expansion(add = c(0.6,0)))+
  scale_fill_manual(labels=c('OpenAlex', 'Scopus', 'Citations of Citings'),
                    values = c('orange2', 'cornflowerblue','#9B59B6'),
                    breaks = 1:3
                    #breaks = c('OpenAlexCitations', 'PyBlioCitations','OpenAlexCitationsOfCiting'
                    )+
  scale_x_log10('Citations',labels=scales::comma, expand = expansion(add = c(0.07,0.1)))+
  
  geom_text(aes(label=scales::comma(value)), position = pos, hjust=1.1, 
            color='white', fontface="bold.italic") +
  theme(legend.title = element_blank(),
        panel.background = element_blank(),
        axis.line = element_line(colour = 'grey19'),
        axis.text = element_text(face = 'bold', size=11),
        axis.title=element_text(face = 'bold.italic', size=10),
        legend.text = element_text(face = 'bold.italic', size=10))

#### FIGURE 3 ####

install.packages("sf")
library(sf)
library(ggplot2)
library(dplyr)
install.packages("rnaturalearthdata")
install.packages("rnaturalearth")
library(rnaturalearth)

w.cit = read.xlsx(exdir, sheet = 2, rowNames = T,cols = c(1,3,4,7))
colnames(w.cit)[1] = "iso_a2"
w.cit = w.cit[!is.na(w.cit$iso_a2),]
w.cit = data.frame(table(w.cit$iso_a2))
colnames(w.cit)[1] = "iso_a2"

world <- ne_countries(scale = "medium", returnclass = "sf")

world_data <- world %>%
  left_join(w.cit, by = "iso_a2")

ggplot(world_data) +
  geom_sf(aes(fill = Freq)) +
  scale_fill_viridis_c(option = "plasma", na.value = "grey90") +
  theme_minimal()

#### FIGURE 4 ####
w.citofcit = read.xlsx(exdir, sheet = 3, cols = c(2:7))
w.citofcit = w.citofcit[!duplicated(w.citofcit) & !is.na(w.citofcit$institution),]
w.citofcit = data.frame(table(w.citofcit$country))
colnames(w.citofcit)[1] = "iso_a2"

world_data <- world %>%
  left_join(w.citofcit, by = "iso_a2")

ggplot(world_data) +
  geom_sf(aes(fill = Freq)) +
  scale_fill_viridis_c(option = "plasma", na.value = "grey90") +
  theme_minimal()

#### FIGURE 5 ####

library(circlize)
c.data = read.xlsx(exdir, sheet = 2)#, cols = c(2,3,4))
c.data = c.data[!is.na(c.data$institution),]
dois = unique(c.data$doi[!is.na(c.data$doi)])
combn_ = function(doi_){
  ists = c.data$institution[c.data$doi == doi_]
  if (length(ists) >= 2){
  comb = data.frame(t(combn(ists,2)))
  colnames(comb) = c('from','to')
  return(comb)
  }
}

a = lapply(dois,combn_)
n = Filter(Negate(is.null), a)
b = bind_rows(Filter(Negate(is.null), a))
b$weight = 1
b = b[!duplicated(b),]
chordDiagram(b, annotationTrack = "grid", 
             preAllocateTracks = list(track.height = max(strwidth(unlist(dimnames(b))))))
circos.track(track.index = 1, panel.fun = function(x, y) {
  circos.text(CELL_META$xcenter, CELL_META$ylim[1], CELL_META$sector.index, 
              facing = "clockwise", cex=.5, niceFacing = TRUE, adj = c(0, 0.5))
}, bg.border = NA)


