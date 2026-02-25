library(ggplot2)
library(reshape2)
library(openxlsx)
#install.packages("sf")
library(sf)
library(ggplot2)
library(dplyr)
#install.packages("rnaturalearthdata")
#install.packages("rnaturalearth")
library(rnaturalearth)
library(ggpubr)
library(circlize)

exdir = "/Users/giuseppedefazio/Documents/RTDA_UniBA/progetti/ELIXIR_citations/out_of_github/Serv_Deliv_Plan_citations/gen26/scopus_openalex/SDP_impact.xlsx"
setwd('/Users/giuseppedefazio/Documents/RTDA_UniBA/progetti/ELIXIR_citations/figures/')

#### FIGURE 3 ####
citations = read.xlsx(exdir, sheet = 1, rowNames = T,cols = c(1,4,6,8))
citations[is.na(citations)] = 0
sum(citations$PyBlioCitations)
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
            position = position_dodge2(width = 1.8), fontface = 'bold') +
  theme(legend.title = element_blank(),
        panel.background = element_blank(),
        axis.line = element_line(colour = 'grey19'),
        axis.text = element_text(face = 'bold', size=11),
        axis.title=element_text(face = 'bold.italic', size=10),
        legend.text = element_text(face = 'bold.italic', size=10))

ggsave('./Figure_3.png', device = 'png',units = 'cm', width = 27, height = 13)

#### FIGURE 4 ####
citdf = read.xlsx(exdir, sheet = 1, rowNames = T,cols = c(1,2,6,7,8))
citdf1 = citdf
citdf1[is.na(citdf1)] = 0
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

ggsave('./Figure_4.png', device = 'png',units = 'cm', width = 25, height = 25)

#### FIGURE 5 ####


w.cit = read.xlsx(exdir, sheet = 2, rowNames = T,cols = c(1,3,4,7))
w.cit[is.na(w.cit)] = 0
colnames(w.cit)[1] = "iso_a2"
w.cit = w.cit[!is.na(w.cit$iso_a2),]
w.cit = data.frame(table(w.cit$iso_a2))
colnames(w.cit)[1] = "iso_a2"

world <- ne_countries(scale = "medium", returnclass = "sf")

world_data <- world %>%
  left_join(w.cit, by = "iso_a2")
w.cit = merge(w.cit, world, by='iso_a2')[,c(1,2,7)]
w.cit = w.cit[order(w.cit$Freq, decreasing = T),]
rownames(w.cit) = 1:dim(w.cit)[1]
#w.cit = w.cit[1:10,]

a = ggplot(world_data) +
  geom_sf(aes(fill = Freq), show.legend = T) +
  scale_fill_viridis_c('Affiliations',option = "plasma", na.value = "grey90",) +
  scale_x_continuous(expand = expansion(add = c(0,0)))+
  scale_y_continuous(expand = expansion(add = c(0,0)))+
  theme(legend.text = element_text(hjust = .5, face = 'bold'),
        legend.title = element_text(hjust = .5, face = 'bold', colour = 'grey10'),
        axis.text = element_blank(),
        axis.ticks = element_blank(),
        panel.background = element_blank(),
        panel.grid.major = element_line(color='grey90'))



b = ggplot(w.cit, aes(x=Freq, y=sov_a3, fill=Freq))+
  geom_bar(stat = 'identity',show.legend = T)+
  geom_text(aes(label = Freq), hjust = - 0.3, fontface='bold')+
  scale_y_discrete(limits=w.cit$sov_a3[1:10], 
                   labels=stringr::str_replace(string = w.cit$sov_a3[1:10],
                                               pattern = '1',
                                               replacement = ''),
                   expand = expansion(add = c(2,2)))+
  scale_x_log10(expand = expansion(add = c(0.1,0.2)))+
  scale_fill_viridis_c('Affiliations',option = "plasma", na.value = "grey90")+
  theme(panel.background = element_blank(),
        axis.title = element_blank(),
        axis.ticks = element_blank(),
        axis.text.x = element_blank(),
        axis.text.y = element_text(face='bold', hjust = .5, color='black')
        )

ggarrange(plotlist = c(a,b), ncol = 2, nrow = 1, 
          labels = c('A)','B)'), common.legend = T,align = 'none')

ggsave('./Figure_5.png', device = 'png',units = 'cm', width = 30, height = 11, bg = 'white')

#### FIGURE 6 ####



members = c("CNR National Research Council of Italy", "CINECA", 
            "AREA Science Park", 
            "Istituto Zooprofilattico Sperimentale del Piemonte, Liguria e Valle d’Aosta",
            "Rizzoli Orthopaedic Institute", "IFOM – The AIRC Institute of Molecular Oncology", 
            "CRS4", "ENEA", "Fondazione Edmund Mach", "GARR", 
            "INFN National Institute for Nuclear Physics", 
            "ISS Istituto Superiore di Sanità", 
            "Stazione Zoologica Anton Dohrn (Anton Dohrn Zoological Station)", 
            "Telethon Institute of Genetics and Medicine", 
            "University of Bari Aldo Moro", "University of Bologna", "University of Florence", 
            "University of Milan", "University of Milano-Bicocca", "University of Naples Federico II", 
            "University of Padua", "University of Parma", "Sapienza University of Rome", 
            "University of Rome Tor Vergata", "University of Salerno", "University of Turin", 
            "University of Tuscia", "University of Verona", "University of Pisa", 
            "Politecnico University of Milan", "Catholic University of the Sacred Heart"
)

c.data = read.xlsx(exdir, sheet = 2)#, cols = c(2,3,4))
c.data = c.data[!is.na(c.data$institution) & c.data$country == 'IT',]
unique(c.data$institution)
dois = unique(c.data$doi[!is.na(c.data$doi)])
combn_ = function(doi_){
  ists = c.data$institution[c.data$doi == doi_]
  #ists = ists[ists %in% members]
  if (length(ists) >= 2){
  comb = data.frame(t(combn(ists,2)))
  colnames(comb) = c('from','to')
  return(comb)
  }
}

a = lapply(dois,combn_)
n = Filter(Negate(is.null), a)
b = bind_rows(Filter(Negate(is.null), a))
b = b[!is.na(b$from) & !is.na(b$to),]
b$weight = 1
b = b[!duplicated(b),]
b$from = stringr::str_split_i(b$from, ',',1)
b$to = stringr::str_split_i(b$to, ',',1)
b$from[b$from == 'Institute of Biomembranes'] = 'National Research Council'
b$to[b$to == 'Institute of Biomembranes'] = 'National Research Council'
b$from[b$from == 'Institute of Biomedical Technologies'] = 'National Research Council'
b$to[b$to == 'Institute of Biomedical Technologies'] = 'National Research Council'
b$from[b$from == 'Neuroscience Institute'] = 'National Research Council'
b$to[b$to == 'Neuroscience Institute'] = 'National Research Council'
b$from[b$from == 'Institute of Food Science'] = 'National Research Council'
b$to[b$to == 'Institute of Food Science'] = 'National Research Council'

b = b[b$from != b$to,]
cnt.to = b[b$to == 'National Research Council',]
colnames(cnt.to) = c('to','from','weight')
cnt.to = cnt.to[,c('from','to','weight')]
b.no.cnrto = b[b$to != 'National Research Council',]
b = rbind(b.no.cnrto,cnt.to)

nodes.order = data.frame(table(rbind(b$from,b$to)))
nodes.order = nodes.order[order(nodes.order$Freq, decreasing = T),]
rownames(nodes.order) = 1:dim(nodes.order)[1]

circos.clear()
png("Figure_6.png", width = 15, height = 15, res = 300,units = 'cm')
circos.par(start.degree=25.5, canvas.xlim = c(-2, 2), canvas.ylim = c(-2, 2))
chordDiagram(b, annotationTrack = "grid", 
             preAllocateTracks = 1,
             order = nodes.order$Var1)

circos.track(track.index = 1, 
             track.margin = circos.par("track.margin"),
             panel.fun = function(x, y) {
  circos.text(CELL_META$xcenter, CELL_META$ylim[1], CELL_META$sector.index, 
              facing = "clockwise", cex=.5, niceFacing = TRUE, adj = c(0, 0.5))
}, bg.border=NA)
dev.off()


#### FIGURE 7 ####
w.citofcit = read.xlsx(exdir, sheet = 3, cols = c(2:7))
w.citofcit = w.citofcit[!duplicated(w.citofcit) & !is.na(w.citofcit$institution),]
w.citofcit = data.frame(table(w.citofcit$country))
w.citofcit[is.na(w.citofcit)] = 0
colnames(w.citofcit)[1] = "iso_a2"

world_data <- world %>%
  left_join(w.citofcit, by = "iso_a2")

w.citofcit = merge(w.citofcit, world, by='iso_a2')[,c(1,2,7)]
w.citofcit = w.citofcit[order(w.citofcit$Freq, decreasing = T),]
rownames(w.citofcit) = 1:dim(w.citofcit)[1]
#w.cit = w.cit[1:10,]

a = ggplot(world_data) +
  geom_sf(aes(fill = Freq), show.legend = T) +
  scale_fill_viridis_c('Affiliations',option = "plasma", na.value = "grey90",
                       labels = scales::label_number(big.mark = ",")) +
  scale_x_continuous(expand = expansion(add = c(0,0)))+
  scale_y_continuous(expand = expansion(add = c(0,0)))+
  theme(legend.text = element_text(face = 'bold', angle = 20, hjust=1),
        legend.title = element_text(hjust = .5, face = 'bold', colour = 'grey10'),
        axis.text = element_blank(),
        axis.ticks = element_blank(),
        panel.background = element_blank(),
        panel.grid.major = element_line(color='grey90'))



b = ggplot(w.citofcit, aes(x=Freq, y=iso_a2, fill=Freq))+
  geom_bar(stat = 'identity',show.legend = T)+
  geom_text(aes(label =scales::comma(Freq)), hjust = - 0.3, fontface='bold')+
  scale_y_discrete(limits=w.citofcit$iso_a2[1:10], 
                   labels=stringr::str_replace(string = w.citofcit$iso_a2[1:10],
                                               pattern = '1',
                                               replacement = ''),
                   expand = expansion(add = c(2,2)))+
  scale_x_log10(expand = expansion(add = c(0.1,1)))+
  scale_fill_viridis_c('Affiliations',option = "plasma", 
                       na.value = "grey90",
                       labels = scales::label_number(big.mark = ","))+
  theme(legend.text = element_text(face = 'bold', angle = 20, hjust=1),
        legend.title = element_text(hjust = .5, face = 'bold', colour = 'grey10'),
        panel.background = element_blank(),
        axis.title = element_blank(),
        axis.ticks = element_blank(),
        axis.text.x = element_blank(),
        axis.text.y = element_text(face='bold', hjust = .5, color='black')
  )

ggarrange(plotlist = c(a,b), ncol = 2, nrow = 1, 
          labels = c('A)','B)'), common.legend = T,align = 'none')

ggsave('./Figure_7.png', device = 'png',units = 'cm', width = 30, height = 11, bg = 'white')
